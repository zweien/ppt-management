"use client";

import Link from "next/link";

export interface SlideCardData {
  id: string;
  page_no: number;
  title: string | null;
  native_text: string | null;
  thumbnail_url: string | null;
  presentation_title?: string | null;
  is_favorite?: boolean;
}

export default function SlideCard({
  slide,
  onOpen,
  onToggleFavorite,
}: {
  slide: SlideCardData;
  onOpen?: (slide: SlideCardData) => void;
  onToggleFavorite?: (slide: SlideCardData) => void;
}) {
  const fav = !!slide.is_favorite;
  return (
    <button
      type="button"
      onClick={() => onOpen?.(slide)}
      disabled={!onOpen}
      className={`bg-white rounded-xl border border-gray-200 overflow-hidden text-left group transition flex flex-col w-full max-w-full ${
        onOpen ? "hover:border-brand-300 hover:shadow-md cursor-pointer" : "cursor-default"
      }`}
    >
      {/* 缩略图:固定宽高比,不随内容伸缩 */}
      <div className="relative aspect-video bg-gray-100 flex items-center justify-center overflow-hidden shrink-0 w-full">
        {slide.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={slide.thumbnail_url} alt={`第${slide.page_no}页`} className="w-full h-full object-contain max-w-full" />
        ) : (
          <span className="text-gray-300 text-sm">无预览</span>
        )}
        {onToggleFavorite && (
          <span
            role="button"
            aria-label={fav ? "取消收藏" : "收藏"}
            title={fav ? "取消收藏" : "收藏"}
            onClick={(e) => {
              e.stopPropagation();
              e.preventDefault();
              onToggleFavorite(slide);
            }}
            className={`absolute top-1.5 right-1.5 w-7 h-7 flex items-center justify-center rounded-full text-base leading-none transition ${
              fav
                ? "bg-yellow-400 text-white opacity-100"
                : "bg-white/80 text-gray-400 hover:bg-white hover:text-yellow-500 opacity-0 group-hover:opacity-100"
            }`}
          >
            ★
          </span>
        )}
      </div>
      {/* 文字区:固定高度,内容截断,保证所有卡片等高 */}
      <div className="p-3 flex flex-col gap-1 h-[88px]">
        <div className="flex items-center gap-2">
          <span className="text-xs bg-brand-100 text-brand-700 px-1.5 py-0.5 rounded shrink-0">P{slide.page_no}</span>
          <span className="text-sm font-medium text-gray-700 truncate">{slide.title || "(无标题)"}</span>
        </div>
        {slide.presentation_title ? (
          <div className="text-xs text-brand-500 truncate" title={slide.presentation_title}>
            📁 {slide.presentation_title}
          </div>
        ) : (
          <div className="text-xs text-transparent select-none">&nbsp;</div>
        )}
        <div className="text-xs text-gray-400 line-clamp-2 leading-relaxed overflow-hidden">
          {slide.native_text?.slice(0, 60) || ""}
        </div>
      </div>
    </button>
  );
}
