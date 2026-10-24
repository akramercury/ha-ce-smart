"""Base entity for CE Smart (Local)."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import CeSmartDataUpdateCoordinator


class CeSmartEntity(CoordinatorEntity[CeSmartDataUpdateCoordinator]):
    """Common base: shares device info and availability for one datapoint."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: CeSmartDataUpdateCoordinator, dp_id: str
    ) -> None:
        """Bind the entity to a coordinator and a datapoint id."""
        super().__init__(coordinator)
        self._dp_id = str(dp_id)
        self._attr_unique_id = f"{coordinator.device_id}_{self._dp_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return shared device registry info."""
        return self.coordinator.device_info

    @property
    def available(self) -> bool:
        """Entity is available when the last poll succeeded and the DP exists."""
        return (
            super().available
            and self.coordinator.data is not None
            and self._dp_id in self.coordinator.data
        )

    def _dp_value(self):
        """Current raw value of this entity's datapoint, or None."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(self._dp_id)
