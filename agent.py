import re
import math
import time as time_module
from datetime import datetime
from typing import Optional, Dict, Any, Callable

class Tool:
    def __init__(self, name: str, description: str, func: Callable):
        self.name = name
        self.description = description
        self.func = func

    def execute(self, **kwargs) -> str:
        try:
            return self.func(**kwargs)
        except Exception as e:
            return f"工具执行错误: {str(e)}"

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, name: str, description: str):
        def decorator(func: Callable):
            self.tools[name] = Tool(name, description, func)
            return func
        return decorator

    def get_tool(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    def list_tools(self) -> Dict[str, str]:
        return {name: tool.description for name, tool in self.tools.items()}

    def match_tool(self, user_input: str) -> Optional[tuple]:
        user_input_lower = user_input.lower()

        if any(k in user_input_lower for k in ['天气', 'weather', '温度']):
            city = self._extract_city(user_input)
            return ('get_weather', {'city': city})
        elif any(k in user_input_lower for k in ['计算', '等于', '多少', '算', '+', '-', '*', '/', '加', '减', '乘', '除']):
            expr = self._extract_expression(user_input)
            if expr:
                return ('calculate', {'expression': expr})
        elif any(k in user_input_lower for k in ['时间', '现在几点', '几点了', '今天', '日期', 'time', 'date']):
            return ('get_current_time', {})

        return None

    def _extract_city(self, text: str) -> str:
        patterns = [
            r'([\u4e00-\u9fa5]+)天气',
            r'天气\s*([\u4e00-\u9fa5]+)',
            r'([\u4e00-\u9fa5]+)\s*的天气',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return '北京'

    def _extract_expression(self, text: str) -> Optional[str]:
        text = text.replace('等于', '=').replace('多少', '').replace('计算', '').replace('是多少', '')
        text = re.sub(r'[\u4e00-\u9fa5]', '', text)
        text = text.strip()
        if re.match(r'^[\d\+\-\*\/\.\(\)\s]+$', text):
            return text
        if '=' in text:
            expr = text.split('=')[-1].strip()
            if re.match(r'^[\d\+\-\*\/\.\(\)\s]+$', expr):
                return expr
        match = re.search(r'[\d\+\-\*\/\.\(\)]+', text)
        if match:
            return match.group()
        return None

registry = ToolRegistry()

@registry.register('get_weather', '获取指定城市的天气信息')
def get_weather(city: str = '北京') -> str:
    try:
        import httpx
        url = f'https://wttr.in/{city}?format=3&lang=zh'
        response = httpx.get(url, timeout=5)
        if response.status_code == 200:
            data = response.text.strip()
            if 'Unknown location' in data:
                return f'未找到城市 "{city}" 的天气信息'
            return f'📍 {city}天气：{data}'
        return f'获取天气失败，请稍后重试'
    except Exception as e:
        return f'天气查询服务暂时不可用：{str(e)}'

@registry.register('calculate', '执行数学计算')
def calculate(expression: str) -> str:
    try:
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expression):
            return '表达式包含非法字符'
        result = eval(expression, {"__builtins__": {}, "math": math})
        if isinstance(result, float) and result.is_integer():
            result = int(result)
        return f'🧮 计算结果：{expression} = {result}'
    except ZeroDivisionError:
        return '错误：除数不能为零'
    except Exception as e:
        return f'计算错误：请检查表达式是否正确'

@registry.register('get_current_time', '获取当前日期和时间')
def get_current_time() -> str:
    now = datetime.now()
    weekdays = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
    return f'🕐 当前时间：{now.strftime("%Y年%m月%d日 %H:%M:%S")} {weekdays[now.weekday()]}'
