from intent_parser import parse_intent

examples = [
    "Run power flow for IEEE 14-bus",
    "Interpret the IEEE 30-bus power flow. Report voltage violations and visualize them.",
    "What if the line between bus 1 and bus 3 is disconnected in case14?",
    "Run case57 pf pandapower",
]

for text in examples:
    req = parse_intent(text)
    print(req.to_json())
    print("-" * 60)
