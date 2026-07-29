"use client";

import Link from "next/link";

export interface SlideCardData {
  id: string;
  page_no: number;
  title: string | null;
  native_text: string | null;
  thumbnail_url: string | null;
  presentation_title?: string | null;
}

export default function SlideCard({
  slide,
  onOpen,
}: {
  slide: SlideCardData;
  onOpen?: (slide: SlideCardData) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onOpen?.(slide)}
      disabled={!onOpen}
      className={`bg-white rounded-xl border border-gray-200 overflow-hidden text-left group transition ${
        onOpen ? "hover:border-brand-300 hover:shadow-md cursor-pointer" : "cursor-default"
      }`}
    >
      <div className="aspect-video bg-gray-100 flex items-center justify-center overflow-hidden">
        {slide.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={slide.thumbnail_url} alt={`第${slide.page_no}页`} className="w-full h-full object-contain" />
        ) : (
          <span className="text-gray-300 text-sm">无预览</span>
        )}
      </div>
      <div className="p-3">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs bg-brand-100 text-brand-700 px-1.5 py-0.5 rounded shrink-0">P{slide.page_no}</span>
          <span className="text-sm font-medium text-gray-700 truncate">{slide.title || "(无标题)"}</span>
        </div>
        {slide.presentation_title && (
          <div className="text-xs text-brand-500 truncate mb-0.5" title={slide.presentation_title}>
            📁 {slide.presentation_title}
          </div>
        )}
        <div className="text-xs text-gray-400 truncate">{slide.native_text?.slice(0, 40) || ""}</div>
      </div>
    </button>
  );
}
