def test_creating_a_post_sends_a_notification_email(admin_client, mailoutbox):
    admin_client.post("/new/", {"title": "mailed", "body": "hi"})

    assert len(mailoutbox) == 1
    assert mailoutbox[0].subject == "New post: mailed"
    assert mailoutbox[0].to == ["editor@example.com"]
