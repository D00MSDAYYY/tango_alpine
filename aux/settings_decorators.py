import weakref
from types import SimpleNamespace
from typing import Type, TypeVar, Any, Dict, Union, Optional
from collections.abc import MutableSequence, MutableMapping, MutableSet

from pydantic import BaseModel
from PySide6.QtCore import QObject, Signal


class ObservableSet(MutableSet):
    def __init__(self, original_set: set, parent: "SettingsWithSignals", field_name: str):
        self._set = original_set
        self._parent = parent
        self._field_name = field_name

    def _wrap_item(self, item):
        return self._parent._wrap_value(item)

    def _unwrap_item(self, item):
        return self._parent._unwrap_value(item)

    def _notify(self):
        # специфичный сигнал поля
        getattr(self._parent, f"{self._field_name}_changed").emit(self._parent._wrap_value(self._set))
        # глобальный сигнал сохранения
        # print("save triggered")
        _saving_trigger.triggered.emit()

    def __contains__(self, value):
        return self._unwrap_item(value) in self._set

    def __iter__(self):
        for item in self._set:
            yield self._wrap_item(item)

    def __len__(self):
        return len(self._set)

    def add(self, value):
        unwrapped = self._unwrap_item(value)
        if unwrapped not in self._set:
            self._set.add(unwrapped)
            self._notify()

    def discard(self, value):
        unwrapped = self._unwrap_item(value)
        if unwrapped in self._set:
            self._set.discard(unwrapped)
            self._notify()

    def __repr__(self):
        return {self._wrap_item(item) for item in self._set}.__repr__()

    # Дополнительные методы для удобства
    def update(self, *others):
        changed = False
        for other in others:
            for item in other:
                unwrapped = self._unwrap_item(item)
                if unwrapped not in self._set:
                    self._set.add(unwrapped)
                    changed = True
        if changed:
            self._notify()

    def clear(self):
        if self._set:
            self._set.clear()
            self._notify()

    def pop(self):
        if not self._set:
            raise KeyError("pop from an empty set")
        item = self._set.pop()
        self._notify()
        return self._wrap_item(item)

    def remove(self, value):
        unwrapped = self._unwrap_item(value)
        if unwrapped not in self._set:
            raise KeyError(value)
        self._set.remove(unwrapped)
        self._notify()

    def get(self, value, default=None):
        unwrapped = self._unwrap_item(value)
        if unwrapped in self._set:
            return self._wrap_item(unwrapped)
        return default


class ObservableList(MutableSequence):
    def __init__(self, original_list: list, parent: "SettingsWithSignals", field_name: str):
        self._list = original_list
        self._parent = parent
        self._field_name = field_name

    def _wrap_item(self, item):
        return self._parent._wrap_value(item)

    def _unwrap_item(self, item):
        return self._parent._unwrap_value(item)

    def _notify(self):
        # специфичный сигнал
        getattr(self._parent, f"{self._field_name}_changed").emit(self._parent._wrap_value(self._list))
        # глобальный сигнал
        # print("save triggered")
        _saving_trigger.triggered.emit()

    def __getitem__(self, index):
        return self._wrap_item(self._list[index])

    def __setitem__(self, index, value):
        old = self._list[index]
        new = self._unwrap_item(value)
        if old == new:
            return
        self._list[index] = new
        self._notify()

    def __delitem__(self, index):
        del self._list[index]
        self._notify()

    def __len__(self):
        return len(self._list)

    def insert(self, index, value):
        self._list.insert(index, self._unwrap_item(value))
        self._notify()

    def __repr__(self):
        return repr([self._wrap_item(item) for item in self._list])

    # Добавим полезные методы
    def append(self, value):
        self.insert(len(self), value)

    def extend(self, values):
        new_values = [self._unwrap_item(v) for v in values]
        if not new_values:
            return
        self._list.extend(new_values)
        self._notify()

    def clear(self):
        if self._list:
            self._list.clear()
            self._notify()

    def pop(self, index=-1):
        val = self._list.pop(index)
        self._notify()
        return self._wrap_item(val)

    def remove(self, value):
        unwrapped = self._unwrap_item(value)
        for i, item in enumerate(self._list):
            if item == unwrapped:
                del self[i]
                return
        raise ValueError("item not in list")

    def reverse(self):
        self._list.reverse()
        self._notify()

    def sort(self, *, key=None, reverse=False):
        self._list.sort(key=key, reverse=reverse)
        self._notify()


class ObservableDict(MutableMapping):
    def __init__(self, original_dict: dict, parent: "SettingsWithSignals", field_name: str):
        self._dict = original_dict
        self._parent = parent
        self._field_name = field_name

    def _wrap_item(self, item):
        return self._parent._wrap_value(item)

    def _unwrap_item(self, item):
        return self._parent._unwrap_value(item)

    def _notify(self):
        getattr(self._parent, f"{self._field_name}_changed").emit(self._parent._wrap_value(self._dict))
        _saving_trigger.triggered.emit()

    def __getitem__(self, key):
        return self._wrap_item(self._dict[key])

    def __setitem__(self, key, value):
        new = self._unwrap_item(value)
        if key in self._dict and self._dict[key] == new:
            return
        self._dict[key] = new
        self._notify()

    def __delitem__(self, key):
        if key in self._dict:
            del self._dict[key]
            self._notify()
        else:
            raise KeyError(key)

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __repr__(self):
        return {k: self._wrap_item(v) for k, v in self._dict.items()}.__repr__()

    def clear(self):
        if self._dict:
            self._dict.clear()
            self._notify()

    def update(self, other=None, **kwargs):
        new_items = {}
        if other:
            if isinstance(other, dict):
                for k, v in other.items():
                    new_items[k] = self._unwrap_item(v)
            else:
                for k, v in other:
                    new_items[k] = self._unwrap_item(v)
        for k, v in kwargs.items():
            new_items[k] = self._unwrap_item(v)
        changed = False
        for k, v in new_items.items():
            if k not in self._dict or self._dict[k] != v:
                self._dict[k] = v
                changed = True
        if changed:
            self._notify()

    def get(self, key, default=None):
        if key in self._dict:
            return self._wrap_item(self._dict[key])
        return default

    def setdefault(self, key, default=None):
        if key in self._dict:
            return self._wrap_item(self._dict[key])
        self[key] = default
        return self._wrap_item(self._dict[key])


class _SavingTrigger(QObject):
    triggered = Signal()


_saving_trigger = _SavingTrigger()


def get_saving_trigger() -> _SavingTrigger:
    """Вернуть глобальный объект, испускающий сигнал при любом изменении настроек"""
    return _saving_trigger


M = TypeVar("M", bound=BaseModel)

# Кэш: id(модели) -> weakref.ref(обёртка)
_wrapper_cache: Dict[int, weakref.ref] = {}


class SettingsWithSignals(QObject):
    def __init__(self, data: Union[M, Dict[str, Any], None] = None, **kwargs):
        super().__init__()
        self._proxies = {}
        model_cls: Type[BaseModel] = getattr(self, "_original_model_class", None)

        if model_cls is None:
            raise TypeError("SettingsWithSignals должен быть создан через settings_with_signals()")

        if isinstance(data, type(self)):
            data_dict = data.model_dump()
            data_dict.update(kwargs)
            self._model = model_cls(**data_dict)
        elif isinstance(data, SettingsWithSignals):
            data_dict = data.model_dump()
            data_dict.update(kwargs)
            self._model = model_cls(**data_dict)
        elif isinstance(data, BaseModel):
            if kwargs:
                data_dict = data.model_dump()
                data_dict.update(kwargs)
                self._model = model_cls(**data_dict)
            else:
                self._model = data
        else:
            # Старое поведение: создаём новую модель из словаря или другого источника
            if isinstance(data, SimpleNamespace):
                data_dict = vars(data)
            elif isinstance(data, dict):
                data_dict = data.copy()
            elif data is not None:
                data_dict = dict(data)
            else:
                data_dict = {}
            data_dict.update(kwargs)
            self._model = model_cls(**data_dict)

        # Регистрируем текущую обёртку в глобальном кэше (по id модели)
        model_id = id(self._model)
        _wrapper_cache[model_id] = weakref.ref(self)
        weakref.finalize(self._model, lambda id_: _wrapper_cache.pop(id_, None), model_id)

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_") or name in ("model_dump", "model_dump_json", "dict", "json"):
            raise AttributeError(name)
        return getattr(self._model, name)

    @classmethod
    def _wrap_value(cls, value: Any) -> Any:
        if isinstance(value, BaseModel) and not isinstance(value, SettingsWithSignals):
            model_id = id(value)
            weak_wrapper = _wrapper_cache.get(model_id)
            if weak_wrapper is not None:
                wrapper = weak_wrapper()
                if wrapper is not None:
                    return wrapper
            wrapper_cls = _get_wrapper_class(type(value))
            if wrapper_cls is not None:
                wrapper = wrapper_cls(value)
                return wrapper
        # Для списков и словарей возвращаем как есть (прокси будет создан в getter)
        return value

    @classmethod
    def _unwrap_value(cls, value: Any) -> Any:
        if isinstance(value, SettingsWithSignals):
            return value._model
        elif isinstance(value, ObservableList):
            return [cls._unwrap_value(item) for item in value._list]
        elif isinstance(value, ObservableDict):
            return {k: cls._unwrap_value(v) for k, v in value._dict.items()}
        elif isinstance(value, ObservableSet):
            return {cls._unwrap_value(item) for item in value._set}
        elif isinstance(value, list):
            return [cls._unwrap_value(item) for item in value]
        elif isinstance(value, dict):
            return {k: cls._unwrap_value(v) for k, v in value.items()}
        elif isinstance(value, set):
            return {cls._unwrap_value(item) for item in value}
        return value

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        unwrapped = self._unwrap_value(self._model)
        return unwrapped.model_dump(**kwargs)

    def model_dump_json(self, **kwargs) -> str:
        unwrapped = self._unwrap_value(self._model)
        return unwrapped.model_dump_json(**kwargs)

    def dict(self, **kwargs) -> Dict[str, Any]:
        return self.model_dump(**kwargs)

    def json(self, **kwargs) -> str:
        return self.model_dump_json(**kwargs)


_wrapper_registry: Dict[Type[BaseModel], Type[SettingsWithSignals]] = {}


def _get_wrapper_class(model_class: Type[BaseModel]) -> Optional[Type[SettingsWithSignals]]:
    return _wrapper_registry.get(model_class)


def settings_with_signals(model_class: Type[M]) -> Type[SettingsWithSignals]:
    class_name = f"{model_class.__name__}WithSignals"

    attrs = {"_original_model_class": model_class}

    for field_name, field_info in model_class.model_fields.items():
        signal_name = f"{field_name}_changed"
        attrs[signal_name] = Signal(object)

        def make_getter(f_name):
            def getter(self: SettingsWithSignals) -> Any:
                value = getattr(self._model, f_name)
                # Отдаём закешированный прокси, если он уже есть
                if f_name in self._proxies:
                    return self._proxies[f_name]

                # 1. Вложенная модель BaseModel (например, _Appearence, _SetupConfig)
                if isinstance(value, BaseModel):
                    wrapped = self._wrap_value(value)   # получит обёртку из кеша или создаст новую
                    self._proxies[f_name] = wrapped      # сильная ссылка, чтобы обёртка не удалилась
                    return wrapped

                # 2. Коллекции (список, словарь, множество)
                if isinstance(value, list):
                    proxy = ObservableList(value, self, f_name)
                    self._proxies[f_name] = proxy
                    return proxy
                elif isinstance(value, dict):
                    proxy = ObservableDict(value, self, f_name)
                    self._proxies[f_name] = proxy
                    return proxy
                elif isinstance(value, set):
                    proxy = ObservableSet(value, self, f_name)
                    self._proxies[f_name] = proxy
                    return proxy

                # 3. Простые значения (строки, числа и т.п.)
                return self._wrap_value(value)

            return getter

        def make_setter(f_name):
            def setter(self: SettingsWithSignals, new_value: Any) -> None:
                new_value_clean = self._unwrap_value(new_value)
                old_value = getattr(self._model, f_name)
                if old_value == new_value_clean:
                    return
                # Удаляем старый прокси, если он был
                if f_name in self._proxies:
                    del self._proxies[f_name]
                setattr(self._model, f_name, new_value_clean)
                emit_value = self._wrap_value(new_value_clean)
                getattr(self, f"{f_name}_changed").emit(emit_value)
                # print("save triggered")
                _saving_trigger.triggered.emit()

            return setter

        attrs[field_name] = property(make_getter(field_name), make_setter(field_name))

    wrapper_cls = type(class_name, (SettingsWithSignals,), attrs)
    _wrapper_registry[model_class] = wrapper_cls
    return wrapper_cls


def with_settings_property(attr_name="_settings", prop_name="settings"):
    def decorator(cls):
        original_init = cls.__init__

        def new_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            if not hasattr(self, attr_name):
                raise AttributeError(f"Class {cls.__name__} must define '{attr_name}' in __init__")

        cls.__init__ = new_init

        def getter(self):
            return getattr(self, attr_name)

        def setter(self, new_settings: SettingsWithSignals):
            old_settings = getattr(self, attr_name, None)
            if old_settings is None:
                setattr(self, attr_name, new_settings)
                return
            for field_name in old_settings._model.model_fields.keys():
                if hasattr(new_settings, field_name):
                    setattr(old_settings, field_name, getattr(new_settings, field_name))

        setattr(cls, prop_name, property(getter, setter))
        return cls

    return decorator
