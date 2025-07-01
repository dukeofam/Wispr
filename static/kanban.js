// Wispr Kanban Board JS (CSP-compliant)
document.addEventListener('DOMContentLoaded', function() {
    // Open Task Modal
    document.querySelectorAll('.open-task-modal').forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            openTaskModal(this.getAttribute('data-task-id'));
        });
    });
    // Project filter badges
    document.querySelectorAll('.project-filter-badge').forEach(badge => {
        badge.addEventListener('click', function() {
            filterByProject(this.getAttribute('data-project-id'));
        });
    });
    const allProjectsBadge = document.getElementById('all-projects-badge');
    if (allProjectsBadge) {
        allProjectsBadge.addEventListener('click', function() {
            clearAllProjectHighlights();
            this.classList.add('active');
            document.querySelectorAll('.task-card').forEach(card => {
                card.style.display = '';
            });
        });
    }
    // Add other event listeners for project CRUD as needed...
});
// ... Move openTaskModal, addComment, loadComments, loadActivity, showToast, project CRUD, and filterByProject functions here from kanban.html ... 