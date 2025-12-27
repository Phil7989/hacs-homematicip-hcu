# custom_components/hcu_integration/event.py
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import asyncio
import logging

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HcuApiClient
from .entity import HcuBaseEntity

if TYPE_CHECKING:
    from . import HcuCoordinator

_LOGGER = logging.getLogger(__name__)


class TriggerableEvent(Protocol):
    """Protocol for event entities that can be triggered by the coordinator."""

    _device_id: str
    _channel_index_str: str

    def handle_trigger(self) -> None:
        """Handle an event trigger from the coordinator."""
        ...


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the event platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][config_entry.entry_id]
    if entities := coordinator.entities.get(Platform.EVENT):
        async_add_entities(entities)


class HcuDoorbellEvent(HcuBaseEntity, HcuEventMixin):
    """Representation of a Homematic IP HCU doorbell event entity."""

    PLATFORM = Platform.EVENT

    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = ["press"]

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict[str, Any],
        channel_index: str,
    ):
        super().__init__(coordinator, client, device_data, channel_index)

        # Use channel label directly without feature name to avoid redundancy
        self._set_entity_name(channel_label=self._channel.get("label"))

        self._attr_unique_id = f"{self._device_id}_{self._channel_index_str}_doorbell_event"

    @callback
    def handle_trigger(self) -> None:
        """Handle an event trigger from the coordinator."""
        self._fire_event("press")


class HcuButtonEvent(HcuBaseEntity, HcuEventMixin):
    """Representation of a Homematic IP HCU button event entity."""

    PLATFORM = Platform.EVENT

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = [
        "press",
        "press_short",
        "press_long",
        "press_long_start",
        "press_long_stop",
    ]

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict[str, Any],
        channel_index: str,
    ):
        super().__init__(coordinator, client, device_data, channel_index)
        self._set_entity_name(channel_label=self._channel.get("label"))
        self._attr_unique_id = f"{self._device_id}_{self._channel_index_str}_button_event"

    @callback
    def handle_trigger(self, event_type: str | None = None) -> None:
        """
        Handle an event trigger from the coordinator.

        Important:
          - We IGNORE event_type=None to avoid firing events from "timestamp/state" updates
            that often happen during startup/reload (classic phantom presses).
          - For real events, we normalize and then fire via _fire_event() which also
            writes state.
        """
        if event_type is None:
            _LOGGER.debug(
                "Ignoring button trigger with event_type=None: %s %s",
                self._device_id,
                self._channel_index_str,
            )
            return

        normalized_event = event_type.lower().replace("key_", "")
        if normalized_event in self._attr_event_types:
            self._fire_event(normalized_event)
        else:
            _LOGGER.debug(
                "Unknown event_type '%s' normalized to '%s' -> fallback 'press': %s %s",
                event_type,
                normalized_event,
                self._device_id,
                self._channel_index_str,
            )
            self._fire_event("press")
