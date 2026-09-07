import { Card, CardBody } from "@/components/ui/Card";

/** A review card (e.g. What worked / What to improve). Demo content in Phase 3B. */
export function PerformanceCard({
  title,
  tone,
  items,
}: {
  title: string;
  tone?: "success" | "warning";
  items: string[];
}) {
  const color =
    tone === "success" ? "text-success" : tone === "warning" ? "text-warning" : undefined;
  return (
    <Card>
      <CardBody>
        <h3 className={color}>{title}</h3>
        <ul className="mt-2 space-y-2 text-sm">
          {items.map((item, i) => (
            <li key={i} className="text-foreground">
              {item}
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}
