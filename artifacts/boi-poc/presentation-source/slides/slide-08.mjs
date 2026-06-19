import { C, bg, footer, kicker, panel, title } from "./common.mjs";

const screenshots = [
  ["BoI Wiki home", "captures/boi-poc/01-boi-wiki-home.png"],
  ["SOP library", "captures/boi-poc/02-sop-library.png"],
  ["Event type detail", "captures/boi-poc/03-event-type-catalog.png"],
  ["Event stream", "captures/boi-poc/04-event-stream.png"],
  ["Workflow status", "captures/boi-poc/05-action-catalog-logs.png"],
  ["Generated BoI", "captures/boi-poc/06-private-boi-corrective-action.png"],
  ["Langflow canvas", "captures/boi-poc/07-langflow-boi-reference-flow.png"],
  ["Kafka topics", "captures/boi-poc/08-kafka-ui-topics.png"],
];

async function screenshotCard(slide, ctx, item, idx) {
  const col = idx % 4;
  const row = Math.floor(idx / 4);
  const x = 56 + col * 300;
  const y = 150 + row * 242;
  const w = 270;
  const h = 210;
  panel(slide, ctx, x, y, w, h, C.white, C.rule);
  ctx.addText(slide, {
    x: x + 12,
    y: y + 10,
    width: w - 24,
    height: 22,
    text: item[0],
    fontSize: 14,
    bold: true,
    color: C.ink,
  });
  await ctx.addImage(slide, {
    path: item[1],
    x: x + 12,
    y: y + 38,
    width: w - 24,
    height: 146,
    fit: "contain",
    alt: item[0],
  });
  ctx.addText(slide, {
    x: x + 12,
    y: y + 188,
    width: w - 24,
    height: 16,
    text: item[1].replace("captures/boi-poc/", ""),
    fontSize: 8,
    color: C.muted,
    typeface: ctx.fonts.mono,
  });
}

export async function slide08(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "EVIDENCE CAPTURE STATUS");
  title(slide, ctx, "Runtime execution is proven with browser evidence, not placeholders.", false, 70, 35);

  for (let idx = 0; idx < screenshots.length; idx += 1) {
    await screenshotCard(slide, ctx, screenshots[idx], idx);
  }

  panel(slide, ctx, 76, 626, 1090, 38, "#EAF7F2", C.green);
  ctx.addText(slide, {
    x: 102,
    y: 636,
    width: 1040,
    height: 18,
    text: "All 8 capture targets passed URL preflight and PNG validation; Langflow canvas and Kafka topics are visible evidence.",
    fontSize: 14,
    bold: true,
    color: C.green,
  });
  footer(slide, ctx, 8, "Source: captures/boi-poc, capture-targets.json, delivery-readiness.json");
  return slide;
}
