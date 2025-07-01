// Wispr Admin Panel JS (CSP-compliant)
document.addEventListener('DOMContentLoaded', function() {
    // Role select auto-submit
    document.querySelectorAll('.role-select').forEach(sel => {
        sel.addEventListener('change', function() {
            this.form.submit();
        });
    });
    // Delete user confirm
    document.querySelectorAll('.delete-user-btn').forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this user? This will also delete all their messages and tasks.')) {
                e.preventDefault();
            }
        });
    });
}); 