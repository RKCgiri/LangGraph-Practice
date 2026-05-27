import openai, inspect
print(openai.__version__)
print('has OpenAI', hasattr(openai, 'OpenAI'))
print('has MCP', hasattr(openai, 'MCP'))
from openai import OpenAI
print([m for m in dir(OpenAI) if 'mcp' in m.lower() or 'tool' in m.lower()])
