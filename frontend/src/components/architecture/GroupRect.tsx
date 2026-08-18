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
        fill={`${group.color}06`}
        stroke={group.color}
        strokeWidth={0.8}
        strokeOpacity={0.2}
        strokeDasharray="5 4"
      />
      <text
        x={bounds.x + 10}
        y={bounds.y + 14}
        style={{
          fontSize: "10px",
          fontWeight: 500,
          fill: group.color,
          fillOpacity: 0.5,
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
