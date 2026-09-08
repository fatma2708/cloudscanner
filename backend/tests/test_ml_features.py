from app.services.ml.features import FEATURE_COLUMNS, resource_to_features


def test_resource_features_have_stable_schema():
    features = resource_to_features(
        {
            "resource_type": "aws_security_group",
            "provider": "aws",
            "service": "security",
            "kind": "security_group",
            "attributes": {
                "ingress": [{"cidr_blocks": ["0.0.0.0/0"]}],
                "encrypted": True,
            },
            "references": ["aws_vpc.main"],
        }
    )
    assert tuple(features) == FEATURE_COLUMNS
    assert features["encryption_enabled"] == 1.0
    assert features["ingress_open_to_world"] == 1.0
    assert features["has_reference"] == 1.0


def test_resource_features_decode_serialized_attributes():
    features = resource_to_features(
        {
            "resource_type": "aws_security_group",
            "provider": "aws",
            "service": "security",
            "kind": "security_group",
            "attributes_json": '{"ingress": [{"cidr_blocks": ["0.0.0.0/0"], "from_port": 22}], "logging": {"enabled": true}}',
        }
    )
    assert features["attribute_count"] == 2.0
    assert features["nested_attribute_count"] > 0
    assert features["has_public_cidr"] == 1.0
    assert features["has_sensitive_port"] == 1.0
    assert features["has_logging_configuration"] == 1.0
