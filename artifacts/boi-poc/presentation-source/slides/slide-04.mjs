import { C, bg, footer, kicker, panel, tableRow, title } from "./common.mjs";

const rows = [
  ["reference", "langflow.boi.reference_flow", "BoI Reference Flow", "7f1ce7c7-7b6f-49cf-bbf6-c990fed400f4"],
  ["analyze", "langflow.equipment.stage_analysis", "BoI Equipment Stage Analysis Flow", "422fa3e4-d09b-4d51-b323-e652a13f2792"],
  ["guide", "langflow.equipment.stage_analysis", "BoI Equipment Stage Analysis Flow", "422fa3e4-d09b-4d51-b323-e652a13f2792"],
  ["correct", "langflow.equipment.stage_analysis", "BoI Equipment Stage Analysis Flow", "422fa3e4-d09b-4d51-b323-e652a13f2792"],
];

export async function slide04(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "LANGFLOW INTEGRATION");
  title(slide, ctx, "Langflow is not just documented; it is invoked by the workflow action log.", false, 70, 35);

  panel(slide, ctx, 72, 166, 1060, 94, "#EEF4FF", C.blue);
  ctx.addText(slide, {
    x: 96,
    y: 188,
    width: 1010,
    height: 52,
    text: "The SSO runtime imports two flows and Action Gateway resolves them by catalog configuration. Four Langflow actions completed with status langflow_invoked in the latest trace.",
    fontSize: 20,
    bold: true,
    color: C.ink,
  });

  tableRow(slide, ctx, 310, ["Stage", "Action key", "Flow name", "Flow ID"], { header: true, widths: [150, 300, 300, 420] });
  rows.forEach((row, idx) => tableRow(slide, ctx, 352 + idx * 46, row, { widths: [150, 300, 300, 420], height: 46 }));

  ctx.addText(slide, {
    x: 76,
    y: 570,
    width: 1060,
    height: 42,
    text: "Canvas evidence is now captured with vercel:agent-browser: the connected Langflow flow shows BoI custom components, Gemma OpenAI-compatible LLM settings, and Action Gateway invocation nodes.",
    fontSize: 15,
    color: C.green,
    bold: true,
  });
  footer(slide, ctx, 4, "Source: summary.json, langflow-flows.json, captures/boi-poc/07-langflow-boi-reference-flow.png");
  return slide;
}
