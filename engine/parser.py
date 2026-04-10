def parse_file(path):

    instructions = []

    with open(path) as f:

        for lineno, line in enumerate(f, 1):

            line = line.strip()

            if not line or line.startswith("#"):
                continue

            inst = line.split()[0]

            allowed = ["FROM", "COPY", "RUN", "WORKDIR", "ENV", "CMD"]

            if inst not in allowed:
                raise Exception(f"Invalid instruction {inst} at line {lineno}")

            instructions.append(line)

    return instructions
