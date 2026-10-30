SELECT g.id, g.pin, g.status, g.quiz_id, q.title AS quiz_title, a.username AS owner
FROM games g
JOIN quizzes q ON q.id = g.quiz_id
JOIN admins a ON a.id = q.admin_id
ORDER BY g.id;