from typing import Type, Dict, TypeVar, ClassVar, Any, Set
from pydantic import BaseModel, field_validator, field_serializer

T = TypeVar("T", bound=BaseModel)


def _dump_model(value: BaseModel, info):
    return value.model_dump(mode=info.mode)


class PolymorphicBase(BaseModel):
    _subtypes: ClassVar[Dict[str, Type["PolymorphicBase"]]] = {}

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)
        # Находим корневой класс иерархии
        root_cls = None
        for base in cls.__mro__[1:]:
            if "_subtypes" in base.__dict__:
                root_cls = base
                break
        if root_cls is None or root_cls is PolymorphicBase:
            cls._subtypes = {}
            root_cls = cls
        else:
            cls._subtypes = root_cls._subtypes
        type_field = cls.model_fields.get("type")
        if type_field and type_field.default is not None:
            root_cls._subtypes[type_field.default] = cls


def _get_all_subclasses(cls):
    subs = set(cls.__subclasses__())
    for sub in cls.__subclasses__():
        subs.update(_get_all_subclasses(sub))
    return subs


def _build_subtype_map(base_cls):
    subtypes = {}
    for sub_cls in _get_all_subclasses(base_cls):
        type_field = sub_cls.model_fields.get("type")
        if type_field and type_field.default:
            subtypes[type_field.default] = sub_cls
    tf = base_cls.model_fields.get("type")
    if tf and tf.default:
        subtypes[tf.default] = base_cls
    return subtypes


# ======================================================================
# Валидатор для словаря Dict[K, BaseModel]
# ======================================================================
def polymorphic_dict_validator(base_model_cls):
    def validator(cls, v: Any) -> dict:
        if not isinstance(v, dict):
            raise ValueError(
                f"Expected dict for '{base_model_cls.__name__}', got {type(v)}"
            )
        subtypes = _build_subtype_map(base_model_cls)
        res = {}
        for k, item in v.items():
            if isinstance(item, base_model_cls):
                res[k] = item
            elif isinstance(item, dict):
                t = item.get("type")
                sub_cls = subtypes.get(t)
                if sub_cls is None:
                    raise ValueError(f"Unknown type '{t}' for key {k}")
                res[k] = sub_cls.model_validate(item)
            else:
                raise ValueError(
                    f"Unexpected element type {type(item)} for key {k}"
                )
        return res

    return validator


def polymorphic_dict_field_handlers(base_model_cls: Type[T], field_name: str):
    """
    Возвращает валидатор и сериализатор для полиморфного словаря
    вида Dict[Any, base_model_cls].
    """
    validator = field_validator(field_name, mode="before")(
        polymorphic_dict_validator(base_model_cls)
    )

    def serialize_polymorphic_dict(self, value: Dict, handler, info):
        return {str(k): _dump_model(v, info) for k, v in value.items()}

    serializer = field_serializer(field_name, mode="wrap")(serialize_polymorphic_dict)
    return validator, serializer


# ======================================================================
# Валидатор для одиночного полиморфного поля
# ======================================================================
def validate_polymorphic_field(base_model_cls: Type[T], v: Any, field_name: str) -> T:
    """
    Преобразует словарь или экземпляр в объект нужного подкласса base_model_cls.
    Можно использовать как отдельно, так и внутри field_validator.
    """
    if isinstance(v, base_model_cls):
        return v
    if not isinstance(v, dict):
        raise ValueError(
            f"Expected dict or {base_model_cls.__name__} for '{field_name}', got {type(v)}"
        )
    subtypes = _build_subtype_map(base_model_cls)
    t = v.get("type")
    sub_cls = subtypes.get(t)
    if sub_cls is None:
        raise ValueError(f"Unknown type '{t}' for field '{field_name}'")
    return sub_cls.model_validate(v)


def polymorphic_field_handler(base_model_cls: Type[T], field_name: str):
    """
    Возвращает валидатор и сериализатор для одиночного полиморфного поля.
    """

    def validator(cls, v):
        return validate_polymorphic_field(base_model_cls, v, field_name)

    field_val = field_validator(field_name, mode="before")(validator)

    def serialize_single(self, value: BaseModel, handler, info):
        return _dump_model(value, info)

    serializer = field_serializer(field_name, mode="wrap")(serialize_single)
    return field_val, serializer


def validate_polymorphic_set(
    base_model_cls: Type[T], v: Any, field_name: str
) -> Set[T]:
    """
    Преобразует список/множество словарей (или уже экземпляров) в множество
    объектов нужного подкласса base_model_cls.
    """
    if not isinstance(v, (list, set, tuple)):
        raise ValueError(f"Expected list/set/tuple for '{field_name}', got {type(v)}")

    subtypes = _build_subtype_map(base_model_cls)
    result = set()
    for item in v:
        if isinstance(item, base_model_cls):
            parsed = item
        elif isinstance(item, dict):
            t = item.get("type")
            sub_cls = subtypes.get(t)
            if sub_cls is None:
                raise ValueError(f"Unknown type '{t}' in set field '{field_name}'")
            parsed = sub_cls.model_validate(item)
        else:
            raise ValueError(
                f"Unexpected element type {type(item)} in set field '{field_name}'"
            )
        try:
            result.add(parsed)
        except TypeError as exc:
            raise ValueError(
                f"Elements of set field '{field_name}' must be hashable. "
                "Use frozen pydantic models or a list field instead."
            ) from exc
    return result


def polymorphic_set_field_handlers(base_model_cls: Type[T], field_name: str):
    """
    Возвращает валидатор и сериализатор для полиморфного множества Set[base_model_cls].
    """

    def validator(cls, v):
        return validate_polymorphic_set(base_model_cls, v, field_name)

    field_val = field_validator(field_name, mode="before")(validator)

    def serialize_set(self, value: Set[BaseModel], handler, info):
        # Сериализуем set в список словарей
        return [_dump_model(item, info) for item in value]

    serializer = field_serializer(field_name, mode="wrap")(serialize_set)
    return field_val, serializer


# Валидатор списка
def validate_polymorphic_list(
    base_model_cls: Type[T], v: Any, field_name: str
) -> list[T]:
    if not isinstance(v, list):
        raise ValueError(f"Expected list for '{field_name}', got {type(v)}")
    subtypes = _build_subtype_map(base_model_cls)
    result = []
    for item in v:
        if isinstance(item, base_model_cls):
            result.append(item)
        elif isinstance(item, dict):
            t = item.get("type")
            sub_cls = subtypes.get(t)
            if sub_cls is None:
                raise ValueError(f"Unknown type '{t}' in list field '{field_name}'")
            result.append(sub_cls.model_validate(item))
        else:
            raise ValueError(
                f"Unexpected element type {type(item)} in list field '{field_name}'"
            )
    return result


def polymorphic_list_field_handlers(base_model_cls: Type[T], field_name: str):
    """Возвращает валидатор и сериализатор для полиморфного списка List[base_model_cls]."""

    def validator(cls, v):
        return validate_polymorphic_list(base_model_cls, v, field_name)

    field_val = field_validator(field_name, mode="before")(validator)

    def serialize_list(self, value: list, handler, info):
        return [_dump_model(item, info) for item in value]

    serializer = field_serializer(field_name, mode="wrap")(serialize_list)
    return field_val, serializer
