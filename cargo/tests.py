from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from partners.models import Company, CompanyMember

from .models import Load


class LoadTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="owner", password="StrongPass123!")
        self.member = user_model.objects.create_user(username="member", password="StrongPass123!")
        self.outsider = user_model.objects.create_user(username="outsider", password="StrongPass123!")
        self.company = Company.objects.create(name="Silk Road Logistics", created_by=self.owner)
        CompanyMember.objects.create(company=self.company, user=self.owner, role="owner", can_post_cargo=True)
        CompanyMember.objects.create(company=self.company, user=self.member, role="member", can_post_cargo=False)
        self.client = APIClient()
        self.payload = {
            "origin": "Andijon",
            "destination": "Namangan",
            "cargo_name": "Pustoy karzinka",
            "vehicle_type": "Tent fura",
            "weight_tons": "1.5",
            "is_price_negotiable": True,
            "contact_phone": "938086599",
            "alternate_phone": "938086599",
        }

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    def test_personal_load_crud_and_display_text(self):
        self.assertEqual(self.client.post("/api/cargo/loads/", self.payload).status_code, 401)
        self.as_user(self.outsider)
        created = self.client.post("/api/cargo/loads/", self.payload)
        self.assertEqual(created.status_code, 201)
        self.assertIsNone(created.data["company"])
        self.assertIn("🚛 ANDIJON ➡️ NAMANGAN 🚛", created.data["display_text"])
        self.assertIn("💰 NARX KELISHILADI!", created.data["display_text"])
        load_id = created.data["id"]
        url = f"/api/cargo/loads/{load_id}/"
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get("/api/cargo/loads/").status_code, 200)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.as_user(self.owner)
        self.assertEqual(self.client.patch(url, {"status": "closed"}).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.as_user(self.outsider)
        replacement = {**self.payload, "destination": "Farg‘ona", "is_price_negotiable": False, "price_amount": "3000000", "currency": "UZS"}
        self.assertEqual(self.client.put(url, replacement).status_code, 200)
        self.assertEqual(self.client.patch(url, {"status": "closed"}).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Load.objects.filter(pk=load_id).exists())

    def test_company_post_requires_membership_permission(self):
        payload = {**self.payload, "company": self.company.pk}
        self.as_user(self.outsider)
        self.assertEqual(self.client.post("/api/cargo/loads/", payload).status_code, 400)
        self.as_user(self.member)
        self.assertEqual(self.client.post("/api/cargo/loads/", payload).status_code, 400)
        membership = CompanyMember.objects.get(company=self.company, user=self.member)
        membership.can_post_cargo = True
        membership.save()
        created = self.client.post("/api/cargo/loads/", payload)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.data["company_name"], self.company.name)
        url = f"/api/cargo/loads/{created.data['id']}/"
        self.assertEqual(self.client.patch(url, {"company": None}, format="json").status_code, 400)
        membership.can_post_cargo = False
        membership.save()
        self.assertEqual(self.client.patch(url, {"status": "closed"}).status_code, 403)
        self.as_user(self.owner)
        self.assertEqual(self.client.patch(url, {"status": "closed"}).status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_fixed_price_requires_amount_and_phone_validation(self):
        self.as_user(self.owner)
        no_price = self.client.post("/api/cargo/loads/", {**self.payload, "is_price_negotiable": False})
        self.assertEqual(no_price.status_code, 400)
        bad_phone = self.client.post("/api/cargo/loads/", {**self.payload, "contact_phone": "123"})
        self.assertEqual(bad_phone.status_code, 400)
        priced = self.client.post("/api/cargo/loads/", {**self.payload, "is_price_negotiable": False, "price_amount": "3000000"})
        self.assertEqual(priced.status_code, 201)
        self.assertIn("3 000 000 UZS", priced.data["display_text"])
