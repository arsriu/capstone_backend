from django.db import models

class UserInfo(models.Model):
    user_id = models.CharField(max_length=50, unique=True, primary_key=True)
    name = models.CharField(max_length=100)
    password = models.CharField(max_length=255)  # 비밀번호는 해시된 값으로 저장됨
    kakaopay_deeplink = models.CharField(max_length=255)
    average_review_score = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)

    class Meta:
        managed = True
        db_table = 'user'
