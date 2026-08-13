from datetime import datetime, timezone

import pytest

from application.scanning.collector import BaseCollector
from domain.resources.models import NormalizedResource
from domain.shared.enums import CloudProvider
from domain.shared.identifiers import ResourceId, TenantId
from infrastructure.cloud.azure.collector import AzureCollector
from infrastructure.cloud.azure.credentials import AzureCredentialConfig
from infrastructure.cloud.azure.errors import AzureCollectionError, AzurePermissionError, AzureServiceError

TENANT = TenantId("acme")
SUBSCRIPTION = "00000000-0000-0000-0000-000000000000"
CLOCK = lambda: datetime(2026, 1, 1, tzinfo=timezone.utc)  # noqa: E731


def make_resource(resource_id: str) -> NormalizedResource:
    return NormalizedResource(
        resource_id=ResourceId(resource_id),
        resource_type="azure_storage_account",
        cloud_provider=CloudProvider.AZURE,
        tenant_id=TENANT,
        region="westeurope",
        attributes={},
        tags={},
        relationships=(),
        collected_at=CLOCK(),
        account_id=SUBSCRIPTION,
    )


class FakeSubCollector:
    resource_type = "fake azure resources"

    def __init__(self, resources=(), error=None):
        self._resources = resources
        self._error = error

    def collect(self):
        if self._error is not None:
            raise self._error
        return self._resources


class FakeClients:
    subscription_id = SUBSCRIPTION
    storage = None
    network = None
    compute = None
    keyvault = None
    monitor = None


class TestAzureCollectorIsAPort:
    def test_azure_collector_satisfies_base_collector(self) -> None:
        assert issubclass(AzureCollector, BaseCollector)

    def test_azure_and_aws_collectors_satisfy_the_same_port(self) -> None:
        # The multi-cloud invariant: both adapters plug into the SAME
        # Phase 2 port, so nothing downstream is provider-aware.
        from infrastructure.cloud.aws.collector import AwsCollector

        assert issubclass(AwsCollector, BaseCollector)
        assert issubclass(AzureCollector, BaseCollector)


class TestAzureCollectorAggregation:
    def test_aggregates_resources_from_every_sub_collector(self) -> None:
        sub_collectors = (
            FakeSubCollector(resources=(make_resource("a"),)),
            FakeSubCollector(resources=(make_resource("b"),)),
        )
        collector = AzureCollector(clients=FakeClients(), tenant_id=TENANT, sub_collectors=sub_collectors)
        assert {str(r.resource_id) for r in collector.collect()} == {"a", "b"}

    def test_empty_subscription_returns_empty_tuple(self) -> None:
        sub_collectors = (FakeSubCollector(resources=()), FakeSubCollector(resources=()))
        collector = AzureCollector(clients=FakeClients(), tenant_id=TENANT, sub_collectors=sub_collectors)
        assert collector.collect() == ()


class TestAzureCollectorIsolation:
    def test_one_failing_service_does_not_prevent_others_from_being_collected(self) -> None:
        sub_collectors = (
            FakeSubCollector(resources=(make_resource("a"),)),
            FakeSubCollector(error=AzurePermissionError("no key vault access")),
        )
        collector = AzureCollector(clients=FakeClients(), tenant_id=TENANT, sub_collectors=sub_collectors)
        assert {str(r.resource_id) for r in collector.collect()} == {"a"}

    def test_all_services_failing_raises_a_diagnosable_error(self) -> None:
        sub_collectors = (
            FakeSubCollector(error=AzurePermissionError("no storage access")),
            FakeSubCollector(error=AzureServiceError("monitor throttled")),
        )
        collector = AzureCollector(clients=FakeClients(), tenant_id=TENANT, sub_collectors=sub_collectors)
        with pytest.raises(AzureCollectionError) as exc_info:
            collector.collect()
        assert isinstance(exc_info.value.__cause__, AzurePermissionError)
        assert "no storage access" in str(exc_info.value)
        assert "monitor throttled" in str(exc_info.value)


class TestAzureCollectorDefaultWiring:
    def test_default_sub_collectors_cover_every_supported_service(self) -> None:
        collector = AzureCollector(clients=FakeClients(), tenant_id=TENANT, clock=CLOCK)
        assert len(collector._sub_collectors) == 5

    def test_subscription_id_is_threaded_into_every_sub_collector(self) -> None:
        collector = AzureCollector(clients=FakeClients(), tenant_id=TENANT, clock=CLOCK)
        assert all(sc._account_id == SUBSCRIPTION for sc in collector._sub_collectors)


class TestAzureCollectorDeterminism:
    def test_collection_is_deterministic(self) -> None:
        sub_collectors = (FakeSubCollector(resources=(make_resource("a"),)),)
        collector = AzureCollector(clients=FakeClients(), tenant_id=TENANT, sub_collectors=sub_collectors)
        assert collector.collect() == collector.collect()


class TestAzureCredentialConfig:
    def test_valid_config(self) -> None:
        config = AzureCredentialConfig(subscription_id=SUBSCRIPTION)
        assert config.subscription_id == SUBSCRIPTION
        assert config.tenant_id is None

    def test_blank_subscription_id_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            AzureCredentialConfig(subscription_id="  ")

    def test_blank_tenant_id_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            AzureCredentialConfig(subscription_id=SUBSCRIPTION, tenant_id="  ")

    def test_config_holds_no_secret_fields(self) -> None:
        # The central rule: this object is a strategy pointer, never a
        # secret. Nothing here can hold a client secret or password.
        config = AzureCredentialConfig(subscription_id=SUBSCRIPTION)
        for forbidden in ("client_secret", "password", "certificate", "key"):
            assert not hasattr(config, forbidden)
