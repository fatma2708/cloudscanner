import {
  Activity,
  Boxes,
  Cpu,
  Database,
  Globe,
  HardDrive,
  Network,
  ShieldCheck,
  Zap,
  type LucideIcon,
} from "lucide-react";

const SERVICE_ICONS: Record<string, LucideIcon> = {
  compute: Cpu,
  database: Database,
  storage: HardDrive,
  network: Network,
  security: ShieldCheck,
  observability: Activity,
  dns: Globe,
  serverless: Zap,
  container: Boxes,
};

const SERVICE_COLORS: Record<string, string> = {
  compute: "#06b6d4",
  database: "#8b5cf6",
  storage: "#10b981",
  network: "#3b82f6",
  security: "#f59e0b",
  observability: "#ec4899",
  dns: "#64748b",
  serverless: "#eab308",
  container: "#94a3b8",
};

interface ServiceMeta {
  icon: string;
  short: string;
  label: string;
}

export const serviceMeta: Record<string, ServiceMeta> = {
  compute: { icon: "dns", short: "EC2", label: "Compute" },
  database: { icon: "database", short: "RDS", label: "Database" },
  storage: { icon: "storage", short: "S3", label: "Storage" },
  network: { icon: "cloud_queue", short: "VPC", label: "Network" },
  security: { icon: "security", short: "IAM", label: "Security" },
  observability: { icon: "monitoring", short: "CW", label: "Observability" },
  dns: { icon: "dns", short: "R53", label: "DNS" },
  serverless: { icon: "bolt", short: "λ", label: "Serverless" },
  container: { icon: "inventory_2", short: "ECS", label: "Container" },
};

export function serviceIcon(service: string): LucideIcon {
  return SERVICE_ICONS[service] ?? Boxes;
}

export function serviceColor(service: string, fallback = "#64748b"): string {
  return SERVICE_COLORS[service] ?? fallback;
}
