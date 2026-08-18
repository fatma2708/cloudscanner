export const PROVIDER_META: Record<
  string,
  { label: string; color: string }
> = {
  aws: { label: "AWS", color: "#ff9900" },
  azurerm: { label: "Azure", color: "#0078d4" },
  google: { label: "Google Cloud", color: "#4285f4" },
  digitalocean: { label: "DigitalOcean", color: "#0069ff" },
  hetzner: { label: "Hetzner", color: "#d50c2d" },
  scaleway: { label: "Scaleway", color: "#f55035" },
  ovh: { label: "OVHcloud", color: "#1230f0" },
  oracle: { label: "Oracle Cloud", color: "#f80000" },
  vultr: { label: "Vultr", color: "#007bfc" },
  linode: { label: "Linode", color: "#02b159" },
};

export function providerColor(provider: string, fallback = "#3b82f6"): string {
  return PROVIDER_META[provider]?.color ?? fallback;
}

export function providerLabel(provider: string): string {
  return PROVIDER_META[provider]?.label ?? provider;
}
