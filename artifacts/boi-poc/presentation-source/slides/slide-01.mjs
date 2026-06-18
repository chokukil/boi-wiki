import { C, bg, footer, kicker, metric, subtitle, title, trace } from "./common.mjs";

export async function slide01(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx, C.ink);
  kicker(slide, ctx, "BOI WIKI E2E EVIDENCE", true);
  title(slide, ctx, "SOP event now runs through Langflow and materializes BoI records.", true, 86, 44);
  subtitle(
    slide,
    ctx,
    "The latest SSO-enabled trace proves the runtime chain from Kafka event to Action Gateway, Langflow invocation, manual handoff, approval gates, and generated BoI documents.",
    true,
    206,
  );

  const x0 = 68;
  const y = 382;
  const w = 150;
  metric(slide, ctx, x0, y, w, String(trace.events), "events in trace", C.green, true);
  metric(slide, ctx, x0 + 190, y, w, String(trace.actions), "action records", "#8BC7FF", true);
  metric(slide, ctx, x0 + 380, y, w, String(trace.generatedBois), "generated BoIs", "#B7E4C7", true);
  metric(slide, ctx, x0 + 570, y, w, String(trace.manualHandoffs), "manual handoffs", "#FFD08A", true);
  metric(slide, ctx, x0 + 760, y, w, String(trace.failed), "failed actions", "#B7E4C7", true);

  ctx.addText(slide, {
    x: 68,
    y: 560,
    width: 980,
    height: 38,
    text: trace.id,
    fontSize: 17,
    color: "#D9E3F0",
    typeface: ctx.fonts.mono,
  });
  ctx.addText(slide, {
    x: 68,
    y: 598,
    width: 980,
    height: 28,
    text: "Smoke command: SERVICE_TOKEN=dev-service-token-change-me python scripts/run_equipment_sop_poc.py",
    fontSize: 12,
    color: "#9CABBD",
    typeface: ctx.fonts.mono,
  });
  footer(slide, ctx, 1, "Source: summary.json, run_equipment_sop_poc.log");
  return slide;
}
