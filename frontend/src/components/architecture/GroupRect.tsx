import type { GraphGroup } from "@/lib/types";
import type { GroupBounds } from "./layout";

interface Props {
  group: GraphGroup;
  bounds: GroupBounds;
}

export function GroupRect({ group, bounds }: Props) {
  return (
    <g>
      <rect
        x={bounds.x}
        y={bounds.y}
        width={bounds.w}
        height={bounds.h}
        rx={12}
        fill={`${group.color}0d`}
        stroke={group.color}
        strokeWidth={1.25}
        strokeOpacity={0.5}
        strokeDasharray="5 4"
      />
      <text
        x={bounds.x + 10}
        y={bounds.y + 14}
        style={{
          fontSize: "11px",
          fontWeight: 600,
          fill: group.color,
          fillOpacity: 0.9,
          paintOrder: "stroke",
          stroke: "white",
          strokeWidth: 3,
          strokeLinejoin: "round",
        }}
        className="select-none"
      >
        {group.label}
      </text>
    </g>
  );
}
