"""Cross-provider catalogs for multi-cloud cost comparison.

For every supported cloud provider we store a small, representative VM catalog
plus storage / networking unit prices. Values are approximate list prices (USD)
as of 2025 and are clearly estimates — the comparison engine's job is relative
positioning ("which provider is cheaper / greener"), not invoice accuracy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VM:
    name: str
    vcpu: int
    ram_gb: float
    hourly: float

    @property
    def monthly(self) -> float:
        return round(self.hourly * 730, 2)


@dataclass(frozen=True)
class ProviderCatalog:
    key: str
    label: str
    region: str
    vms: tuple[VM, ...]
    block_storage_gb: float
    object_storage_gb: float
    lb_monthly: float
    nat_monthly: float
    eip_monthly: float
    egress_gb: float
    managed_db_factor: float = 1.5
    carbon_g_per_kwh: float = 500.0
    availability: str = "High"
    notes: tuple[str, ...] = ()
    monthly_free_tier: float = 0.0


def _vms(*specs: tuple[str, int, float, float]) -> tuple[VM, ...]:
    return tuple(VM(name, vcpu, ram, hourly) for name, vcpu, ram, hourly in specs)


PROVIDERS: dict[str, ProviderCatalog] = {
    "aws": ProviderCatalog(
        key="aws",
        label="AWS",
        region="us-east-1",
        vms=_vms(
            ("t3.micro", 2, 1, 0.0104),
            ("t3.small", 2, 2, 0.0208),
            ("t3.medium", 2, 4, 0.0416),
            ("t3.large", 2, 8, 0.0832),
            ("t4g.large", 2, 8, 0.0672),
            ("t3.xlarge", 4, 16, 0.1664),
            ("m5.large", 2, 8, 0.096),
            ("m5.xlarge", 4, 16, 0.192),
            ("m6i.xlarge", 4, 16, 0.192),
            ("m5.2xlarge", 8, 32, 0.384),
            ("m5.4xlarge", 16, 64, 0.768),
            ("m5.8xlarge", 32, 128, 1.536),
            ("c5.xlarge", 4, 8, 0.17),
            ("c6i.xlarge", 4, 8, 0.17),
            ("r5.xlarge", 4, 32, 0.252),
            ("r5.2xlarge", 8, 64, 0.504),
        ),
        block_storage_gb=0.08,
        object_storage_gb=0.023,
        lb_monthly=16.43,
        nat_monthly=32.22,
        eip_monthly=3.60,
        egress_gb=0.09,
        managed_db_factor=1.6,
        carbon_g_per_kwh=485,
        availability="Highest",
        notes=("Largest ecosystem", "300+ services", "Most mature FinOps tooling"),
    ),
    "azure": ProviderCatalog(
        key="azure",
        label="Azure",
        region="East US",
        vms=_vms(
            ("B1s", 1, 1, 0.0122),
            ("B2s", 2, 4, 0.0416),
            ("B2ms", 2, 8, 0.0832),
            ("B4ms", 4, 16, 0.1664),
            ("B8ms", 8, 32, 0.3328),
            ("D2as_v5", 2, 8, 0.096),
            ("D4as_v5", 4, 16, 0.192),
            ("D8as_v5", 8, 32, 0.384),
            ("D16as_v5", 16, 64, 0.768),
            ("D32as_v5", 32, 128, 1.536),
            ("E2as_v5", 2, 16, 0.126),
            ("E4as_v5", 4, 32, 0.252),
            ("F4as_v5", 4, 8, 0.17),
        ),
        block_storage_gb=0.081,
        object_storage_gb=0.018,
        lb_monthly=18.40,
        nat_monthly=28.00,
        eip_monthly=3.30,
        egress_gb=0.087,
        managed_db_factor=1.5,
        carbon_g_per_kwh=350,
        availability="Highest",
        notes=("Best Microsoft/Windows integration", "Strong hybrid story"),
    ),
    "google": ProviderCatalog(
        key="google",
        label="Google Cloud",
        region="us-central1",
        vms=_vms(
            ("e2-micro", 2, 1, 0.0076),
            ("e2-small", 2, 2, 0.0159),
            ("e2-medium", 2, 4, 0.0319),
            ("e2-standard-2", 2, 8, 0.0671),
            ("e2-standard-4", 4, 16, 0.1342),
            ("e2-standard-8", 8, 32, 0.2684),
            ("e2-standard-16", 16, 64, 0.5368),
            ("n2-standard-2", 2, 8, 0.0971),
            ("n2-standard-4", 4, 16, 0.1942),
            ("n2-standard-8", 8, 32, 0.3884),
            ("n2-standard-16", 16, 64, 0.7768),
            ("c3-standard-4", 4, 16, 0.18),
            ("c3-standard-8", 8, 32, 0.36),
        ),
        block_storage_gb=0.10,
        object_storage_gb=0.020,
        lb_monthly=18.0,
        nat_monthly=25.0,
        eip_monthly=0.0,
        egress_gb=0.12,
        managed_db_factor=1.6,
        carbon_g_per_kwh=120,
        availability="Highest",
        notes=("Best-in-class global network", "Carbon-free energy targets by 2030"),
    ),
    "digitalocean": ProviderCatalog(
        key="digitalocean",
        label="DigitalOcean",
        region="nyc1",
        vms=_vms(
            ("s-1vcpu-1gb", 1, 1, 0.0082),
            ("s-1vcpu-2gb", 1, 2, 0.0164),
            ("s-2vcpu-2gb", 2, 2, 0.0247),
            ("s-2vcpu-4gb", 2, 4, 0.0329),
            ("s-4vcpu-8gb", 4, 8, 0.0658),
            ("s-2vcpu-8gb", 2, 8, 0.0658),
            ("s-4vcpu-16gb", 4, 16, 0.1315),
            ("s-8vcpu-32gb", 8, 32, 0.263),
            ("s-12vcpu-48gb", 12, 48, 0.3945),
            ("s-16vcpu-64gb", 16, 64, 0.526),
        ),
        block_storage_gb=0.10,
        object_storage_gb=0.005,
        lb_monthly=20.0,
        nat_monthly=15.0,
        eip_monthly=4.0,
        egress_gb=0.01,
        managed_db_factor=1.5,
        carbon_g_per_kwh=400,
        availability="Good",
        notes=("Simple predictable pricing", "Great for startups"),
    ),
    "hetzner": ProviderCatalog(
        key="hetzner",
        label="Hetzner",
        region="fsn1",
        vms=_vms(
            ("CPX11", 2, 2, 0.0056),
            ("CPX21", 3, 4, 0.0104),
            ("CPX31", 4, 8, 0.0155),
            ("CPX41", 8, 16, 0.0278),
            ("CPX51", 16, 32, 0.0537),
            ("CX22", 2, 4, 0.0068),
            ("CX32", 4, 8, 0.0126),
            ("CCX23", 4, 16, 0.0239),
            ("CCX33", 8, 32, 0.0479),
            ("CCX43", 16, 64, 0.0959),
            ("CCX53", 24, 96, 0.1439),
            ("CCX63", 32, 128, 0.1919),
        ),
        block_storage_gb=0.05,
        object_storage_gb=0.005,
        lb_monthly=3.5,
        nat_monthly=0.0,
        eip_monthly=1.2,
        egress_gb=0.0,
        managed_db_factor=1.3,
        carbon_g_per_kwh=210,
        availability="Good",
        notes=("Aggressive pricing", "20 TB free egress on some plans"),
        monthly_free_tier=4.0,
    ),
    "scaleway": ProviderCatalog(
        key="scaleway",
        label="Scaleway",
        region="fr-par",
        vms=_vms(
            ("DEV1-S", 2, 2, 0.0047),
            ("DEV1-M", 3, 4, 0.0090),
            ("DEV1-L", 4, 8, 0.0180),
            ("DEV1-XL", 8, 16, 0.0360),
            ("GP1-XS", 2, 4, 0.0102),
            ("GP1-S", 4, 8, 0.0205),
            ("GP1-M", 8, 16, 0.0410),
            ("GP1-L", 16, 32, 0.0820),
            ("PRO2-XXS", 2, 8, 0.0090),
            ("PRO2-XS", 4, 16, 0.0180),
            ("PRO2-S", 8, 32, 0.0360),
            ("PRO2-M", 16, 64, 0.0720),
        ),
        block_storage_gb=0.08,
        object_storage_gb=0.02,
        lb_monthly=11.0,
        nat_monthly=8.0,
        eip_monthly=2.0,
        egress_gb=0.01,
        managed_db_factor=1.4,
        carbon_g_per_kwh=110,
        availability="Good",
        notes=("French cloud with green datacenters", "Great EU latency"),
    ),
    "ovh": ProviderCatalog(
        key="ovh",
        label="OVHcloud",
        region="GRA9",
        vms=_vms(
            ("d2-2", 2, 4, 0.0055),
            ("d2-4", 4, 8, 0.0110),
            ("d2-8", 8, 16, 0.0220),
            ("d2-15", 12, 30, 0.0410),
            ("b2-7", 2, 7, 0.0078),
            ("b2-15", 4, 15, 0.0156),
            ("b2-30", 8, 30, 0.0330),
            ("b2-60", 16, 60, 0.0660),
            ("r2-15", 4, 15, 0.0170),
            ("r2-30", 8, 30, 0.0350),
            ("r2-60", 16, 60, 0.0700),
        ),
        block_storage_gb=0.06,
        object_storage_gb=0.01,
        lb_monthly=8.0,
        nat_monthly=0.0,
        eip_monthly=1.0,
        egress_gb=0.01,
        managed_db_factor=1.4,
        carbon_g_per_kwh=260,
        availability="Good",
        notes=("European data sovereignty", "Great value on CPU-heavy loads"),
    ),
    "oracle": ProviderCatalog(
        key="oracle",
        label="Oracle Cloud",
        region="us-ashburn-1",
        vms=_vms(
            ("VM.Standard.E2.1.Micro", 1, 1, 0.0),
            ("VM.Standard.A1.Flex", 4, 24, 0.0200),
            ("VM.Standard.E2.1", 1, 8, 0.0050),
            ("VM.Standard.E2.2", 2, 16, 0.0100),
            ("VM.Standard.E2.4", 4, 32, 0.0200),
            ("VM.Standard.E4.Flex", 8, 64, 0.0400),
            ("VM.Standard.E5.Flex", 16, 128, 0.0800),
            ("VM.Standard3.Flex", 8, 128, 0.0440),
            ("VM.Standard3.Flex", 16, 256, 0.0880),
        ),
        block_storage_gb=0.025,
        object_storage_gb=0.026,
        lb_monthly=18.0,
        nat_monthly=20.0,
        eip_monthly=0.0,
        egress_gb=0.0085,
        managed_db_factor=1.4,
        carbon_g_per_kwh=350,
        availability="Good",
        notes=("Ampere ARM free tier", "Aggressive pricing vs. big three"),
        monthly_free_tier=3.0,
    ),
    "vultr": ProviderCatalog(
        key="vultr",
        label="Vultr",
        region="ewr",
        vms=_vms(
            ("vc2-1c-1gb", 1, 1, 0.0082),
            ("vc2-1c-2gb", 1, 2, 0.0164),
            ("vc2-2c-4gb", 2, 4, 0.0329),
            ("vc2-2c-8gb", 2, 8, 0.0658),
            ("vc2-4c-8gb", 4, 8, 0.0658),
            ("vc2-4c-16gb", 4, 16, 0.1315),
            ("vc2-8c-32gb", 8, 32, 0.2630),
            ("vc2-16c-64gb", 16, 64, 0.5260),
            ("vc2-16c-96gb", 16, 96, 0.7890),
        ),
        block_storage_gb=0.10,
        object_storage_gb=0.005,
        lb_monthly=10.0,
        nat_monthly=0.0,
        eip_monthly=1.0,
        egress_gb=0.01,
        managed_db_factor=1.5,
        carbon_g_per_kwh=380,
        availability="Good",
        notes=("32+ bare metal + cloud regions", "Predictable flat pricing"),
    ),
    "linode": ProviderCatalog(
        key="linode",
        label="Linode",
        region="us-east",
        vms=_vms(
            ("g6-nanode-1", 1, 1, 0.0068),
            ("g6-standard-1", 1, 2, 0.0164),
            ("g6-standard-2", 2, 4, 0.0329),
            ("g6-standard-4", 4, 8, 0.0658),
            ("g6-standard-6", 6, 16, 0.0986),
            ("g6-standard-8", 8, 32, 0.1315),
            ("g6-standard-16", 16, 64, 0.2630),
            ("g6-standard-20", 20, 96, 0.3288),
            ("g6-standard-32", 32, 128, 0.5260),
        ),
        block_storage_gb=0.10,
        object_storage_gb=0.005,
        lb_monthly=10.0,
        nat_monthly=0.0,
        eip_monthly=0.0,
        egress_gb=0.01,
        managed_db_factor=1.5,
        carbon_g_per_kwh=380,
        availability="Good",
        notes=("Now part of Akamai", "Simple, developer-friendly"),
    ),
}


def all_providers() -> list[ProviderCatalog]:
    return list(PROVIDERS.values())


def get_provider(key: str) -> ProviderCatalog:
    return PROVIDERS.get(key, PROVIDERS["aws"])


def cheapest_vm(catalog: ProviderCatalog, vcpu: int, ram_gb: float) -> VM:
    """Cheapest VM in the catalog meeting vcpu & ram requirements."""
    candidates = [v for v in catalog.vms if v.vcpu >= vcpu and v.ram_gb >= ram_gb - 0.01]
    if not candidates:
        biggest = max(catalog.vms, key=lambda v: v.vcpu)
        return VM(biggest.name, biggest.vcpu, biggest.ram_gb, biggest.hourly)
    return min(candidates, key=lambda v: v.hourly)
