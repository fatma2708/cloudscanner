import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CrimFindingBlock, CrimInlineChip, CrimSummaryChips, crimCategoryLabel } from "./crim";
import type { CrimClassification } from "@/lib/types";

const model = "CRIM-v4.2";

function cls(
  category: CrimClassification["category"],
  confidence: number,
  abstained = false,
): CrimClassification {
  return { category, confidence, abstained, reason: abstained ? "ML classification uncertain" : null, model };
}

describe("CRIM confident classification", () => {
  const block = (c: CrimClassification) => <CrimFindingBlock classification={c} />;

  it("A: NETWORK_SECURITY 0.827 → category, 82.7% confidence, and CRIM-v4.2 shown", () => {
    render(block(cls("NETWORK_SECURITY", 0.827)));
    expect(screen.getByText("Network Security")).toBeInTheDocument();
    expect(screen.getByText(/Confidence 82\.7%/)).toBeInTheDocument();
    expect(screen.getByText(/CRIM-v4\.2/)).toBeInTheDocument();
  });

  it("B: DATA_SECURITY 0.7535 → Data Security", () => {
    render(block(cls("DATA_SECURITY", 0.7535)));
    expect(screen.getByText("Data Security")).toBeInTheDocument();
    expect(screen.getByText(/Confidence 75\.4%/)).toBeInTheDocument();
  });

  it("C: OBSERVABILITY 0.878 → Observability", () => {
    render(block(cls("OBSERVABILITY", 0.878)));
    expect(screen.getByText("Observability")).toBeInTheDocument();
    expect(screen.getByText(/Confidence 87\.8%/)).toBeInTheDocument();
  });

  it("I: resource-level classification renders on the resource surface without duplication of the model name", () => {
    render(<CrimInlineChip classification={cls("OBSERVABILITY", 0.878)} />);
    expect(screen.getByText("ML")).toBeInTheDocument();
    expect(screen.getByText(/87\.8%/)).toBeInTheDocument();
    expect(screen.queryByText(/CRIM-v4\.2/)).not.toBeInTheDocument();
  });
});

describe("CRIM abstention", () => {
  it("D: abstained → 'ML classification uncertain', no category, confidence + model shown", () => {
    render(<CrimFindingBlock classification={cls(null, 0.4998, true)} />);
    expect(screen.getByText("ML classification uncertain")).toBeInTheDocument();
    expect(screen.queryByText(/Network Security/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Data Security/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Observability/)).not.toBeInTheDocument();
    expect(screen.getByText(/Confidence 50%/)).toBeInTheDocument();
    expect(screen.getAllByText(/CRIM-v4\.2/).length).toBeGreaterThan(0);
  });
});

describe("CRIM unavailable", () => {
  it("expresses unavailability when passed explicitly to the finding block", () => {
    render(<CrimFindingBlock classification={null} unavailable />);
    expect(screen.getByText("ML classification unavailable")).toBeInTheDocument();
  });
});

describe("Backward compatibility with old responses", () => {
  it("renders nothing when the crim summary is absent", () => {
    const { container } = render(<CrimSummaryChips summary={null} />);
    expect(container.firstChild).toBeNull();
    expect(screen.queryByText(/ML classification/)).not.toBeInTheDocument();
  });
});

describe("Multi-resource / unresolved target", () => {
  it("G: null classification with no unavailability → neutral 'ML classification uncertain', no fabricated category", () => {
    render(<CrimInlineChip classification={{ category: null, confidence: 0, abstained: false, reason: null, model }} />);
    expect(screen.getByLabelText("ML classification uncertain")).toBeInTheDocument();
    expect(screen.queryByText(/Network Security/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Data Security/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Observability/)).not.toBeInTheDocument();
  });
});

describe("CRIM summary chips", () => {
  it("builds chips strictly from backend values without inventing stats", () => {
    render(<CrimSummaryChips summary={{ name: model, version: "4.2", classified: 24, abstained: 8, unclassified: 0 }} />);
    expect(screen.getByText(/ML classification/)).toBeInTheDocument();
    expect(screen.getByText("Classified 24")).toBeInTheDocument();
    expect(screen.getByText("Abstained 8")).toBeInTheDocument();
    expect(screen.queryByText(/Not classified/)).not.toBeInTheDocument();
  });

  it("shows unavailable state from crim.ml_unavailable", () => {
    render(<CrimSummaryChips summary={{ ml_unavailable: true }} />);
    expect(screen.getByText("ML classification unavailable")).toBeInTheDocument();
  });
});

describe("Category label mapping", () => {
  it("maps backend categories to display labels", () => {
    expect(crimCategoryLabel("NETWORK_SECURITY")).toBe("Network Security");
    expect(crimCategoryLabel("DATA_SECURITY")).toBe("Data Security");
    expect(crimCategoryLabel("OBSERVABILITY")).toBe("Observability");
    expect(crimCategoryLabel(null)).toBeNull();
    expect(crimCategoryLabel("UNKNOWN_CATEGORY")).toBeNull();
  });
});