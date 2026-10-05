"use client";

import { useEffect, useRef, useState } from "react";
import { useLanguage } from "@/lib/i18n";

type PdfJsPreviewProps = { src: string };

export default function PdfJsPreview({ src }: PdfJsPreviewProps) {
  const { translate: t } = useLanguage();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [status, setStatus] = useState("PDF hazırlanıyor...");
  const [pageCount, setPageCount] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function renderFirstPage() {
      try {
        setStatus("PDF.js çiziyor...");
        const pdfjs = await import("pdfjs-dist/legacy/build/pdf.mjs");
        // PDF.js accepts disableWorker at runtime for this small, single-page
        // preview; the current type definition omits the compatibility flag.
        const documentTask = pdfjs.getDocument({ url: src, disableWorker: true } as any);
        const document = await documentTask.promise;
        if (cancelled) return;

        setPageCount(document.numPages);
        const page = await document.getPage(1);
        const viewport = page.getViewport({ scale: 1.35 });
        const canvas = canvasRef.current;
        const context = canvas?.getContext("2d");
        if (!canvas || !context || cancelled) return;

        canvas.width = viewport.width;
        canvas.height = viewport.height;
        await page.render({ canvas, canvasContext: context, viewport }).promise;
        if (!cancelled) setStatus("");
      } catch {
        if (!cancelled) setStatus("PDF.js önizlemesi yüklenemedi; indirme bağlantısını kullanın.");
      }
    }

    void renderFirstPage();
    return () => {
      cancelled = true;
    };
  }, [src]);

  return (
    <div className="space-y-2 rounded-xl border border-slate-700 bg-slate-950/80 p-3">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>{t(status || "PDF.js önizleme hazır")}</span>
        {pageCount > 0 && <span>{pageCount} {t("sayfa")}</span>}
      </div>
      <div className="max-h-[520px] overflow-auto rounded-lg bg-slate-200 p-2">
        <canvas ref={canvasRef} className="mx-auto h-auto max-w-full shadow-lg" aria-label={t("ATS CV PDF önizlemesi")} />
      </div>
    </div>
  );
}
