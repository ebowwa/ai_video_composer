def format_bash_command(tokens):
    formatted_command = []
    indent = " " * 4
    for token in tokens:
        if token.startswith("-"):
            formatted_command.append("\n" + indent + token)
        else:
            formatted_command.append(" " + token)
    return "".join(formatted_command)
