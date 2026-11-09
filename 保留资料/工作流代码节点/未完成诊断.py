def main(package_error: str, storyboard_errors_json: str, motion_errors_json: str, brief_ok: bool) -> dict:
    def text(value):
        try:
            return str(value or "").strip()
        except Exception:
            return ""

    reasons = []
    package_error = text(package_error)
    storyboard_errors = text(storyboard_errors_json)
    motion_errors = text(motion_errors_json)

    if package_error and package_error not in ("[]", "{}"):
        reasons.append("批准包（A16）：" + package_error)
    if storyboard_errors and storyboard_errors not in ("[]", "{}"):
        reasons.append("分镜（A09）：" + storyboard_errors[:400])
    if motion_errors and motion_errors not in ("[]", "{}"):
        reasons.append("动效（A11）：" + motion_errors[:400])
    if not reasons:
        reasons.append("没有拿到具体错误信息；多半是某个节点输出被截断或返回了空内容。")

    lines = ["# 这次没有出片", "", "按下面列出的那一步去修：", ""]
    lines.extend("- " + item for item in reasons)
    lines += [
        "",
        "## 常见原因",
        "- 某个节点输出的 JSON 不合法（最常见，通常是输出太长被截断）",
        "- 口播为空，或口播门禁未通过",
        "- 分镜 / 动效数量不足",
        "",
        "## 处理",
        "1. 在 Dify 里看哪个节点标红，把它的输出贴回来。",
        "2. 或直接重跑一次；同一位置反复失败就是提示词或输出长度问题，不是偶发。",
    ]
    return {"output": "\n".join(lines)}
