select * from [dbo].[users]
select * from [dbo].[tickets]
SELECT * FROM [TicketFlow].[dbo].[ticket_activity]
SELECT * FROM [TicketFlow].[dbo].[chat_error_log]

declare @p1 int
set @p1=2
exec sp_prepexec @p1 output,N'@P1 int,@P2 int',N'SELECT id, ticket_number, requester_id, assignee_id, title, description, category, priority, status, created_at, updated_at FROM tickets WHERE (requester_id = @P1 OR assignee_id = @P2) ORDER BY created_at DESC, id DESC',1,1
select @p1