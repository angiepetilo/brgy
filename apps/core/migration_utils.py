"""Helpers shared by data migrations (use only historical models from ``apps``)."""
import logging

from apps.core.validators import is_valid_ph_mobile, normalize_ph_mobile

logger = logging.getLogger('apps.migrations')


def normalize_phone_field(apps, app_label, model_name, field):
    """
    Rewrite ``field`` on every row to 09XXXXXXXXX where possible.

    Valid and blank values are untouched. Values that cannot be normalized are
    left unchanged (never deleted); their ids are printed and logged so an
    admin can fix them. Returns (changed_count, [invalid ids]).
    """
    Model = apps.get_model(app_label, model_name)
    changed, invalid = 0, []
    rows = Model.objects.exclude(**{field: ''}).exclude(**{f'{field}__isnull': True})
    for pk, raw in rows.values_list('pk', field).iterator():
        if is_valid_ph_mobile(raw):
            continue
        normalized = normalize_ph_mobile(raw)
        if normalized is None:
            invalid.append(pk)
            continue
        Model.objects.filter(pk=pk).update(**{field: normalized})
        changed += 1
    if invalid:
        message = (
            f'[{app_label}.{model_name}.{field}] {len(invalid)} value(s) could not be normalized '
            f'to 09XXXXXXXXX and were left unchanged; fix them by hand. ids: {invalid}'
        )
        print(f'\n  {message}')
        logger.warning(message)
    return changed, invalid
