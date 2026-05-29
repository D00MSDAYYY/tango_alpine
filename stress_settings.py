from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from alpine import AlpineSettings
from aux.polymorphic_field_handlers import (
    PolymorphicBase,
    _build_subtype_map,
    validate_polymorphic_set,
)
from aux.settings_decorators import get_saving_trigger, settings_with_signals
from cnl.cnl import _ChannelSettings


class _SignalCounter:
    def __init__(self):
        self.count = 0

    def bump(self):
        self.count += 1

    def delta_after(self, action):
        before = self.count
        action()
        return self.count - before


class _NestedModel(BaseModel):
    title: str = "nested"
    value: int = 1


NestedSettings = settings_with_signals(_NestedModel)


class _StressModel(BaseModel):
    name: str = "stress"
    nested: _NestedModel = Field(default_factory=_NestedModel)
    values: list[int] = Field(default_factory=lambda: [1, 2, 3])
    mapping: dict[str, object] = Field(default_factory=dict)


StressSettings = settings_with_signals(_StressModel)


class _PolyBase(PolymorphicBase):
    type: Literal["PolyBase"] = "PolyBase"


class _PolyChild(_PolyBase):
    type: Literal["PolyChild"] = "PolyChild"
    payload: int = 1


def _assert(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def _load_config() -> dict:
    config_path = Path(__file__).with_name("config.json")
    with config_path.open(encoding="utf-8") as file:
        return json.load(file)


def test_observable_collections(iterations: int):
    counter = _SignalCounter()
    get_saving_trigger().triggered.connect(counter.bump)

    settings = StressSettings()

    _assert(
        counter.delta_after(lambda: settings.values.remove(1)) == 1,
        "ObservableList.remove() must emit exactly one save signal",
    )
    _assert(list(settings.values) == [2, 3], "ObservableList.remove() changed data incorrectly")

    _assert(
        counter.delta_after(lambda: settings.values.extend([4, 5, 6])) == 1,
        "ObservableList.extend() must emit exactly one save signal",
    )
    _assert(list(settings.values) == [2, 3, 4, 5, 6], "ObservableList.extend() changed data incorrectly")

    _assert(
        counter.delta_after(lambda: settings.mapping.__setitem__("none_value", None)) == 1,
        "ObservableDict must emit when adding a missing key with None value",
    )
    _assert(
        "none_value" in settings.mapping._dict,
        "ObservableDict lost a missing key with None value",
    )

    _assert(
        counter.delta_after(lambda: settings.mapping.setdefault("default_none")) == 1,
        "ObservableDict.setdefault(None) must emit when key is missing",
    )
    _assert(settings.mapping._dict["default_none"] is None, "ObservableDict.setdefault(None) stored wrong value")

    nested_first = settings.nested
    nested_second = settings.nested
    _assert(nested_first is nested_second, "Nested wrapper must be cached per field")

    for index in range(iterations):
        settings.name = f"name-{index}"
        settings.nested.value = index
        settings.values.append(index)
        settings.values.pop()
        settings.mapping[f"k{index}"] = {"value": index}
        dumped = settings.model_dump()
        _assert(dumped["nested"]["value"] == index, "Nested model dump is stale")
        _assert(dumped["mapping"][f"k{index}"]["value"] == index, "Dict model dump is stale")


def test_wrapper_construction():
    original = StressSettings(name="original")
    copied = StressSettings(original, name="copied")
    from_model = StressSettings(original._model, name="from_model")

    _assert(copied.name == "copied", "Wrapper construction from wrapper ignored kwargs")
    _assert(from_model.name == "from_model", "Wrapper construction from BaseModel ignored kwargs")
    _assert(original.name == "original", "Copy construction mutated the original wrapper")


def test_polymorphic_config(iterations: int):
    config_data = _load_config()
    expected_types = {
        "ChannelSettings",
        "DummyChannelSettings",
        "ModbusChannelSettings",
        "TPEChannelSettings",
    }

    subtype_map = _build_subtype_map(_ChannelSettings)
    _assert(
        expected_types.issubset(subtype_map),
        f"Subtype map is missing channel types: {expected_types - set(subtype_map)}",
    )
    _assert(
        expected_types.issubset(_ChannelSettings._subtypes),
        f"PolymorphicBase registry is missing channel types: {expected_types - set(_ChannelSettings._subtypes)}",
    )

    for _ in range(iterations):
        settings = AlpineSettings(**config_data)
        dumped = settings.model_dump()
        json_text = settings.model_dump_json(indent=2)

        _assert(settings.cnls_setts, "Config must contain at least one channel")
        _assert("cnls_setts" in dumped, "Serialized settings lost cnls_setts")
        _assert("TPEChannelSettings" in json_text, "JSON serialization lost subtype data")


def test_polymorphic_errors():
    subtype_map = _build_subtype_map(_PolyBase)
    _assert(subtype_map["PolyChild"] is _PolyChild, "Local pydantic subtype registration failed")
    _assert(_PolyBase._subtypes["PolyChild"] is _PolyChild, "PolymorphicBase._subtypes registration failed")

    try:
        validate_polymorphic_set(_PolyBase, [{"type": "PolyChild"}], "items")
    except ValueError as exc:
        _assert("must be hashable" in str(exc), "Set validator returned an unclear unhashable-model error")
    else:
        raise AssertionError("Set validator must reject non-hashable pydantic models")


def main():
    parser = argparse.ArgumentParser(description="Stress-test settings wrappers and polymorphic handlers.")
    parser.add_argument(
        "--iterations",
        type=int,
        default=300,
        help="Number of repeated mutation/serialization cycles.",
    )
    args = parser.parse_args()

    _assert(args.iterations > 0, "--iterations must be positive")

    test_observable_collections(args.iterations)
    test_wrapper_construction()
    test_polymorphic_config(args.iterations)
    test_polymorphic_errors()

    print(f"OK: settings stress-test passed ({args.iterations} iterations)")


if __name__ == "__main__":
    main()
