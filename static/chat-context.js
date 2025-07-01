// Wispr chat context loader (CSP-safe)
(function() {
    const body = document.body;
    window.CHAT_CONTEXT = {
        username: body.getAttribute('data-username'),
        user_id: parseInt(body.getAttribute('data-user-id'), 10),
        role: body.getAttribute('data-role')
    };
})(); 