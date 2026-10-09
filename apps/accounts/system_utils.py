"""
Small, dependency-free helpers shared by the System Settings services and views.

Checkbox decision (one place, documented here)
----------------------------------------------
HTML checkboxes do not post anything when unchecked, and the old code used
``bool(data.get('is_active', True))`` which could never turn a flag off ('0' is a
truthy string and a missing key meant True). The rules are now:

* ``parse_bool(data, key, default)`` is pure parsing. ``on/true/1/yes`` is True,
  ``false/0/off/no`` (and an empty string) is False, case-insensitive. A missing key,
  ``None`` or an unrecognised value returns ``default`` so garbage never flips state.
* Services pass ``default`` as follows:
    - CREATE: the documented default of the field (``is_active`` True, ``is_free`` True,
      ``expires`` True, ``notify_on_post`` False, ``is_system`` False).
    - UPDATE: the object's CURRENT value, so programmatic callers may send a partial
      payload without silently changing flags they did not mention.
* Browser forms always contain their checkboxes, so for them "key missing" means
  "unchecked". The views call ``with_unchecked_checkboxes`` which adds ``'0'`` for every
  checkbox the form owns but did not post. Together this means an unchecked box always
  switches the flag off, on create and on update.
"""

TRUE_VALUES = frozenset({'1', 'true', 'on', 'yes'})
FALSE_VALUES = frozenset({'0', 'false', 'off', 'no', ''})


def parse_bool(data, key, default):
    """Return the boolean stored under ``key`` in ``data`` or ``default`` if absent/unknown."""
    if data is None or key not in data:
        return default
    value = data.get(key)
    if isinstance(value, (list, tuple)):  # plain dict carrying getlist-style values: last wins
        value = value[-1] if value else None
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in TRUE_VALUES:
            return True
        if text in FALSE_VALUES:
            return False
        return default
    return bool(value)


def with_unchecked_checkboxes(data, keys):
    """
    Copy of a form payload where every checkbox in ``keys`` that was not posted
    is set to '0' (unchecked). Use only for forms that actually render those checkboxes.
    """
    cleaned = data.copy()
    for key in keys:
        if key not in cleaned:
            cleaned[key] = '0'
    return cleaned


def safe_int(value, default, minimum=0):
    """Parse ``value`` as an int, fall back to ``default`` and never go below ``minimum``."""
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        number = default
    return max(minimum, number)
