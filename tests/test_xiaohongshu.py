from nsg_price.xiaohongshu import body_text_before_tags, split_body_and_tags


def test_split_body_and_tags_removes_final_tag_line():
    body, tags = split_body_and_tags(
        "\u6b63\u6587\u7b2c\u4e00\u884c\n\u6b63\u6587\u7b2c\u4e8c\u884c\n#Switch #\u6e38\u620f\u56de\u6536"
    )

    assert body == "\u6b63\u6587\u7b2c\u4e00\u884c\n\u6b63\u6587\u7b2c\u4e8c\u884c"
    assert tags == ["Switch", "\u6e38\u620f\u56de\u6536"]


def test_body_text_before_tags_adds_blank_line_when_tags_exist():
    assert body_text_before_tags("line one\nline two", ["Switch"]) == "line one\nline two\n\n"
    assert body_text_before_tags("line one", []) == "line one"
