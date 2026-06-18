import { C, bg, footer, kicker, panel, title } from "./common.mjs";

export async function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "EVIDENCE CAPTURE STATUS");
  title(slide, ctx, "Runtime execution is proven; browser screenshots are the remaining evidence gap.", false, 70, 35);

  const slots = [
    ["Workflow Status", "http://localhost:8000/workflows/equipment-anomaly/status"],
    ["Generated BoI", "http://localhost:8000/docs/boi:private:100001:..."],
    ["Event Stream", "http://localhost:8000/events?trace_id=..."],
    ["Langflow Canvas", "http://localhost:7860/flow/422fa3e4-..."],
    ["Kafka UI", "http://localhost:8081/"],
    ["Action Raw Detail", "http://localhost:8000/actions/raw/..."],
  ];

  slots.forEach((slot, idx) => {
    const col = idx % 3;
    const row = Math.floor(idx / 3);
    const x = 70 + col * 380;
    const y = 210 + row * 150;
    panel(slide, ctx, x, y, 330, 104, "#FFFFFF00", C.amber);
    ctx.addShape(slide, { x: x + 18, y: y + 18, width: 294, height: 2, fill: C.amber });
    ctx.addText(slide, { x: x + 18, y: y + 34, width: 294, height: 24, text: slot[0], fontSize: 16, bold: true, color: C.ink });
    ctx.addText(slide, { x: x + 18, y: y + 64, width: 294, height: 26, text: slot[1], fontSize: 10, color: C.muted, typeface: ctx.fonts.mono });
  });

  panel(slide, ctx, 76, 548, 1090, 58, "#FFF6E8", C.amber);
  ctx.addText(slide, {
    x: 102,
    y: 564,
    width: 1040,
    height: 28,
    text: "Chrome Browser Use rejected localhost access by enterprise policy. The capture pass must be rerun after policy is opened; no alternate browser path was used.",
    fontSize: 16,
    bold: true,
    color: C.amber,
  });
  footer(slide, ctx, 8, "Source: evidence-ledger.md, Chrome Browser Use policy rejection");
  return slide;
}
