
from django.db import models
from accounts.models import CustomUser

class ApprovalWorkflow(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class ApprovalStep(models.Model):
    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.CASCADE, related_name='steps')
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField()

    class Meta:
        ordering = ['order']
        unique_together = ['workflow', 'order']

    def __str__(self):
        return f"{self.workflow.name} - {self.name}"

class Document(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    submitted_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='submitted_documents')
    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.CASCADE)
    current_step = models.ForeignKey(ApprovalStep, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    def move_to_next_step(self):
        current_step_order = self.current_step.order
        next_step = ApprovalStep.objects.filter(
            workflow=self.workflow,
            order__gt=current_step_order
        ).order_by('order').first()

        if next_step:
            self.current_step = next_step
            self.status = 'in_review'
        else:
            self.status = 'approved'
        self.save()

    def reject(self):
        self.status = 'rejected'
        self.save()
        # Delete all pending approvals
        # self.approvals.filter(is_approved=None).delete()

    # def resubmit(self):
    #     self.status = 'in_review'
    #     self.save()
    #      # Delete all pending approvals
    #     self.approvals.filter(is_approved=None).delete()



class Approval(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='approvals')
    step = models.ForeignKey(ApprovalStep, on_delete=models.CASCADE)
    approver = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    is_approved = models.BooleanField(null=True, default=None)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.document.title} - {self.step.name} - {self.approver.username}"


