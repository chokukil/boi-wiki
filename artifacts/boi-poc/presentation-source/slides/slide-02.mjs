import { C, bg, connector, footer, kicker, node, subtitle, title } from "./common.mjs";

export async function slide02(presentation, ctx) {
  const slide = presentation.slides.add();
  bg(slide, ctx);
  kicker(slide, ctx, "RUNTIME ARCHITECTURE");
  title(slide, ctx, "The executable surfaces are peers behind one governed event chain.", false, 70, 36);
  subtitle(slide, ctx, "No stage requires Python hardcoding of equipment behavior: SOP metadata, event catalog, and action catalog describe the runtime path.");

  const y = 270;
  node(slide, ctx, 60, y, 155, 105, "Kafka", "boi.events topic emits equipment.alarm.raised.v1", C.green);
  connector(slide, ctx, 215, y + 52, 265, y + 52);
  node(slide, ctx, 265, y, 165, 105, "Event Router", "routes by event type and SOP stage metadata", C.green);
  connector(slide, ctx, 430, y + 52, 480, y + 52);
  node(slide, ctx, 480, y, 170, 105, "Action Gateway", "catalog-driven API, MCP, Langflow, broker, manual dispatch", C.blue);
  connector(slide, ctx, 650, y + 52, 705, y + 52);
  node(slide, ctx, 705, y - 72, 195, 78, "API / MCP", "PoC endpoints are replaceable by catalog URL/tool config", C.blue);
  node(slide, ctx, 705, y + 24, 195, 78, "Langflow", "reference and stage-analysis flows invoked by action log", C.blue);
  node(slide, ctx, 705, y + 120, 195, 78, "Manual", "human handoff and approval state stays explicit", C.amber);
  connector(slide, ctx, 900, y + 52, 955, y + 52, C.green);
  node(slide, ctx, 955, y, 210, 105, "BoI Wiki", "stage-specific Private BoIs + OKF links + workflow status", C.green);

  ctx.addText(slide, {
    x: 78,
    y: 494,
    width: 1050,
    height: 76,
    text: "Execution proof: the latest trace contains materialized BoI records, invoked API actions, invoked Langflow flows, published downstream events, and approval_required high-risk actions.",
    fontSize: 20,
    color: C.ink,
    bold: true,
  });
  footer(slide, ctx, 2, "Source: workflow-status.json, data/action_catalog/actions.yaml");
  return slide;
}
