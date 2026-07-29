"""批量造数据用于性能压测(清单18:20,000 页规模)。

复制现有 slides(含 text_search + embedding)到新的虚拟 version,达到目标页数。
不经过真实解析/渲染,直接复制行(带新 UUID),保证 text_search/embedding 可用。
"""
import sys
sys.path.insert(0, "/app")
import uuid
from app.db.session import SessionLocal
from app.models import Presentation, PresentationVersion, Slide, SlideEmbedding
from sqlalchemy import text as sa_text

TARGET_SLIDES = 20000

db = SessionLocal()
# 找一个有 embedding 的 slide 作模板
template = (
    db.query(Slide).join(SlideEmbedding, SlideEmbedding.slide_id == Slide.id)
    .filter(Slide.text_search.isnot(None)).first()
)
if not template:
    print("no template slide with embedding found")
    db.close(); sys.exit(1)
src_version = db.get(PresentationVersion, template.version_id)
src_pres = db.get(Presentation, src_version.presentation_id)
print(f"template: pres={src_pres.title}, slide page={template.page_no}")

# 收集所有有 embedding 的 slides 作模板池
pool = (
    db.query(Slide).join(SlideEmbedding, SlideEmbedding.slide_id == Slide.id)
    .filter(Slide.text_search.isnot(None)).all()
)
print(f"template pool: {len(pool)} slides")

# 创建一个虚拟 presentation + version 用于承载造的数据
bulk_pres = Presentation(title="__PERF_TEST_BULK__", owner_id=src_pres.owner_id, page_count=0)
db.add(bulk_pres); db.flush()
bulk_ver = PresentationVersion(
    presentation_id=bulk_pres.id, version_no=1, source_object_key=src_version.source_object_key,
    sha256="0" * 64, page_count=0, status="BASIC_READY", file_size=0, original_filename="bulk.pptx",
)
db.add(bulk_ver); db.flush()
bulk_pres.current_version_id = bulk_ver.id
db.commit()

existing = db.query(Slide).filter(Slide.version_id == bulk_ver.id).count()
need = TARGET_SLIDES - existing
print(f"existing bulk slides: {existing}, need to add: {need}")
if need <= 0:
    print("already at target"); db.close(); sys.exit(0)

# 批量插入:复制模板池循环
import itertools
batch_size = 500
inserted = 0
page_no = existing + 1
emb_src = {s.id: db.query(SlideEmbedding).filter(SlideEmbedding.slide_id == s.id).first() for s in pool}

for i in range(0, need, batch_size):
    chunk = min(batch_size, need - i)
    for j in range(chunk):
        tpl = pool[(i + j) % len(pool)]
        new_sid = str(uuid.uuid4())
        db.add(Slide(
            id=new_sid, version_id=bulk_ver.id, page_no=page_no,
            title=tpl.title, native_text=tpl.native_text, notes_text=tpl.notes_text,
            content_json=tpl.content_json, preview_object_key=tpl.preview_object_key,
            thumbnail_object_key=tpl.thumbnail_object_key, text_search=tpl.text_search,
            fingerprint=tpl.fingerprint, visual_phash=tpl.visual_phash,
            parse_status="success", ai_status="success",
        ))
        # 复制 embedding
        emb = emb_src.get(tpl.id)
        if emb and emb.embedding is not None:
            db.flush()
            new_emb = SlideEmbedding(
                slide_id=new_sid, model_config_id=emb.model_config_id,
                source_hash=emb.source_hash, status="success",
            )
            db.add(new_emb); db.flush()
            db.execute(sa_text("UPDATE slide_embeddings SET embedding = (SELECT embedding FROM slide_embeddings WHERE id=:src) WHERE id=:dst"),
                       {"src": emb.id, "dst": new_emb.id})
        page_no += 1
        inserted += 1
    db.commit()
    print(f"  inserted {inserted}/{need}")

bulk_ver.page_count = page_no - 1
bulk_pres.page_count = page_no - 1
db.commit()
total = db.query(Slide).count()
print(f"DONE. total slides now: {total}")
db.close()
