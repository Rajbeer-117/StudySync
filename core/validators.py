"""Validate both file extensions and file signatures for Phase 1 uploads."""
from pathlib import Path
from django.core.exceptions import ValidationError

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 3 * 1024 * 1024


def validate_pdf(value):
    if not value:
        return
    if Path(value.name).suffix.lower() != '.pdf':
        raise ValidationError('Only PDF notes are allowed.')
    if value.size > MAX_PDF_BYTES:
        raise ValidationError('PDF notes must be 5 MB or smaller.')
    position = value.tell()
    value.seek(0)
    signature = value.read(5)
    value.seek(position)
    if signature != b'%PDF-':
        raise ValidationError('This file is not a valid PDF.')


def validate_image(value):
    if not value:
        return
    if Path(value.name).suffix.lower() not in ('.jpg', '.jpeg', '.png'):
        raise ValidationError('Profile photos must be JPG or PNG.')
    if value.size > MAX_IMAGE_BYTES:
        raise ValidationError('Profile photos must be 3 MB or smaller.')
    from PIL import Image
    try:
        position = value.tell()
        value.seek(0)
        image = Image.open(value)
        if image.format not in ('JPEG', 'PNG'):
            raise ValidationError('The photo contents must be JPG or PNG.')
        image.verify()
        value.seek(position)
    except (OSError, ValueError, SyntaxError) as exc:
        raise ValidationError('Upload a valid JPG or PNG image.') from exc
