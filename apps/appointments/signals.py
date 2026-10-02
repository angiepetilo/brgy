import qrcode
from qrcode.image.pil import PilImage
from io import BytesIO
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.files.base import ContentFile
from apps.appointments.models import Appointment, IssuedDocumentLog


@receiver(post_save, sender=Appointment)
def generate_issued_document_log(sender, instance, created, **kwargs):
    """
    Automatically creates an IssuedDocumentLog with a unique control number
    and programmatic verification QR code when an appointment transitions to 'completed'.
    """
    if instance.status == Appointment.STATUS_COMPLETED:
        if not hasattr(instance, 'issued_log'):
            year = timezone.now().year
            count = IssuedDocumentLog.objects.filter(issued_at__year=year).count() + 1
            control_number = f"BRGY-{year}-{count:04d}"

            # Ensure uniqueness
            while IssuedDocumentLog.objects.filter(control_number=control_number).exists():
                count += 1
                control_number = f"BRGY-{year}-{count:04d}"

            log = IssuedDocumentLog(
                appointment=instance,
                control_number=control_number,
                issued_to=instance.resident,
                issued_by=instance.processed_by,
            )

            # Programmatically render QR code image containing verification URL
            verify_payload = f"/appointments/verify/{control_number}/"
            qr = qrcode.QRCode(
                version=1,
                box_size=8,
                border=2,
                image_factory=PilImage,
            )
            qr.add_data(verify_payload)
            qr.make(fit=True)
            img = qr.make_image(fill_color="#1e1b4b", back_color="white")

            buffer = BytesIO()
            img.save(buffer, format='PNG')
            file_name = f"qr_{control_number}.png"
            log.qr_code.save(file_name, ContentFile(buffer.getvalue()), save=False)
            log.save()
