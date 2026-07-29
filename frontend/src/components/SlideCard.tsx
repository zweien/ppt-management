"use client";

import { Star } from "lucide-react";
import { cn } from "@/lib/cn";

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
  selected,
}: {
  slide: SlideCardData;
  onOpen?: (slide: SlideCardData) => void;
  onToggleFavorite?: (slide: SlideCardData) => void;
  selected?: boolean;
}) {
  const fav = !!slide.is_favorite;
  return (
    <button
      type="button"
      onClick={() => onOpen?.(slide)}
      disabled={!onOpen}
      className={cn(
        "group relative bg-surface text-ink rounded-md overflow-hidden text-left transition flex flex-col w-full",
        selected
          ? "shadow-e4 ring-1 ring-primary"
          : "shadow-e2 hover:shadow-e3",
        onOpen ? "cursor-pointer" : "cursor-default",
      )}
    >
      {/* Thumbnail: fixed aspect, object-contain (never crop slide). */}
      <div className="relative aspect-video bg-canvas-soft-2 flex items-center justify-center overflow-hidden shrink-0">
        {slide.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={slide.thumbnail_url}
            alt={`第${slide.page_no}页`}
            className="w-full h-full object-contain max-w-full"
          />
        ) : (
          <span className="text-mute text-sm font-mono">no preview</span>
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
            className={cn(
              "absolute top-2 right-2 w-7 h-7 flex items-center justify-center rounded-full border backdrop-blur transition",
              fav
                ? "bg-warning-soft text-warning-deep border-warning/30"
                : "bg-canvas/80 text-mute border-hairline hover:text-warning-deep hover:bg-canvas opacity-0 group-hover:opacity-100",
            )}
          >
            <Star className="w-4 h-4" fill={fav ? "currentColor" : "none"} />
          </span>
        )}
      </div>
      {/* Text region: fixed height so all cards stay equal-height. */}
      <div className="p-3 flex flex-col gap-1 h-[88px]">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-mute px-1.5 py-0.5 bg-canvas-soft-2 rounded shrink-0">
            P{slide.page_no}
          </span>
          <span className="text-sm font-medium text-ink truncate">{slide.title || "(无标题)"}</span>
        </div>
        {slide.presentation_title ? (
          <div className="text-xs text-link truncate" title={slide.presentation_title}>
            {slide.presentation_title}
          </div>
        ) : (
          <div className="text-xs text-transparent select-none">&nbsp;</div>
        )}
        <div className="text-xs text-mute line-clamp-2 leading-relaxed overflow-hidden">
          {slide.native_text?.slice(0, 60) || ""}
        </div>
      </div>
    </button>
  );
}
