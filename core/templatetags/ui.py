"""Small presentation helpers for templates (avatars)."""
import zlib

from django import template

register = template.Library()

_TITLES = {'dr', 'prof', 'professor', 'mr', 'mrs', 'ms', 'mx', 'sir', 'madam'}


@register.filter
def initials(value, fallback='?'):
    """'Dr. Aznam Yacoub' -> 'AY'; 'Kobti' -> 'K'; titles are skipped; works on any object via str()."""
    words = [w for w in str(value or '').replace('.', ' ').replace('-', ' ').split() if w]
    words = [w for w in words if w.lower() not in _TITLES] or words
    letters = [w[0] for w in words if w[0].isalpha()]
    if not letters:
        return fallback
    return (letters[0] + letters[-1] if len(letters) > 1 else letters[0]).upper()


@register.filter
def avatar_hue(value):
    """A stable hue (0-359) per name so every person keeps the same avatar colour."""
    return zlib.crc32(str(value or '').strip().lower().encode()) % 360
