# -*- coding: utf-8 -*-
import re
import argparse
from pathlib import Path

"""
Markdown 数学公式自动标注工具 v2.1
更新日志：
1. 修复了 $$...$$ 换行公式块被误伤的 Bug。
2. 新增 'undo' 模式，可一键撤销高亮状态下的修改。
3. [New] 强制规范化行内公式：自动去除 $ 与内容之间的空格 (例如 $ x $ -> $x$)，确保 MkDocs 渲染正常。
"""

# --- 配置区域 ---

# 1. 强数学特征变量（单字母），在上下文中极大概率是公式
MATH_VARS = set([
    'x', 'y', 'z', 'u', 'v', 'w', 
    'k', 'i', 'j', 't', 'n', 'm',
    'A', 'B','D', 'F', 'H', 'P', 'Q', 'R', 'K', 'I', 'S', 'Z', 'X', 'Y', 'L','U', 'N', 'M', 'E', 'T', 'C', 'G',
# 矩阵常用
    'theta', 'mu', 'sigma', 'alpha', 'beta', 'gamma', 'lambda', 'delta', 'phi', 'omega'
])

# 2. 肯定是普通英文单词的（黑名单）
ENGLISH_STOPWORDS = set([
     'I', 'in', 'is', 'at', 'to', 'of', 'on', 'if', 'or', 'by', 'we', 'it', 'so', 'as', 'be',
    'slam', 'matrix', 'vector', 'filter', 'model', 'update', 'predict', 'estimate', 'map'
])

# 3. 高亮标记符号
MARKER_START = "=="
MARKER_END = "=="

# --- 正则表达式编译 ---

# 保护区域正则：
# 1. 代码块 ```...```
# 2. 行内代码 `...`
# 3. 显示公式块 $$...$$ (使用 [\s\S] 允许匹配换行符) -- 必须放在行内公式 $...$ 之前匹配
# 4. 行内公式 $...$
PROTECT_PATTERN = re.compile(r'(```[\s\S]*?```|`[^`\n]+`|\$\$[\s\S]*?\$\$|\$[^\$\n]+\$)')

# 复杂公式特征：含 _, ^, \, {} 或 运算符号
COMPLEX_MATH_PATTERN = re.compile(r'(?:[a-zA-Z0-9\\]+[_\^\{][a-zA-Z0-9_\^\{\}\-\+\\]+)')

# 简单的运算特征 (如 k-1, k+1)
OPERATION_PATTERN = re.compile(r'\b[a-zA-Z0-9]+\s*[\+\=\<\>]\s*[a-zA-Z0-9]+\b|\b[kxyzmn]\s*-\s*[0-9a-z]\b') 

def normalize_inline_math(text):
    """
    清洗行内公式内部的空格。
    MkDocs/MathJax 通常要求 $x$ 紧凑，不能写成 $ x $。
    此函数会利用 PROTECT_PATTERN 重新扫描文本，只处理 $...$ 块。
    """
    parts = PROTECT_PATTERN.split(text)
    new_parts = []

    for i, part in enumerate(parts):
        # 奇数索引是保护区域 (code, $$, $)
        if i % 2 == 1:
            # 辨别：只有以 $ 开头且不以 $$ 开头的才是行内公式
            if part.startswith('$') and not part.startswith('$$'):
                # 去除首尾 $，strip() 去空，再加回 $
                content = part[1:-1].strip()
                new_parts.append(f"${content}$")
            else:
                # 代码块或 $$...$$ 保持原样
                new_parts.append(part)
        else:
            # 普通文本保持原样
            new_parts.append(part)
    
    return "".join(new_parts)

def apply_highlight(text):
    """
    模式 1: Highlight
    识别潜在公式 -> 添加 $ -> 添加 ==高亮==
    最后执行 normalize_inline_math 确保格式紧凑
    """
    parts = PROTECT_PATTERN.split(text)
    new_parts = []

    for i, part in enumerate(parts):
        if i % 2 == 1:
            new_parts.append(part)
            continue
        
        def replace_func(match):
            word = match.group(0)
            
            # 防重
            if MARKER_START in word or "$" in word:
                return word

            is_math = False
            
            if COMPLEX_MATH_PATTERN.search(word):
                is_math = True
            elif OPERATION_PATTERN.search(word):
                is_math = True
            elif word in MATH_VARS and word not in ENGLISH_STOPWORDS:
                is_math = True
            
            if is_math:
                # 注意：这里直接生成紧凑的公式
                return f"{MARKER_START}${word.strip()}${MARKER_END}"
            else:
                return word

        token_pattern = re.compile(r'[a-zA-Z0-9_\\^\{\}\-\+\=\<\>]+')
        processed_part = token_pattern.sub(replace_func, part)
        new_parts.append(processed_part)

    result = "".join(new_parts)
    # 再次清洗以防万一（比如处理了原文档里本身就带空格的公式）
    return normalize_inline_math(result)

def remove_highlight(text):
    """
    模式 2: Clean
    移除 == 标记，保留 $，并确保无多余空格
    """
    # 移除高亮
    pattern = re.compile(re.escape(MARKER_START) + r'(\$[^\$]+\$)' + re.escape(MARKER_END))
    cleaned_text = pattern.sub(r'\1', text)
    
    # 再次确保所有公式内部无空格
    return normalize_inline_math(cleaned_text)

def undo_changes(text):
    """
    模式 3: Undo
    撤销所有带有高亮标记的修改，回退到原始文本
    """
    pattern = re.compile(re.escape(MARKER_START) + r'\$(.*?)\$' + re.escape(MARKER_END))
    return pattern.sub(r'\1', text)

def main():
    parser = argparse.ArgumentParser(description="Markdown 公式自动标注助手 v2.1")
    parser.add_argument("file", help="输入的 Markdown 文件路径")
    parser.add_argument("--mode", choices=['highlight', 'clean', 'undo'], default='highlight', 
                        help="highlight: 自动加$并高亮; clean: 移除高亮保留$; undo: 撤销加$和高亮")
    
    args = parser.parse_args()
    file_path = Path(args.file)

    if not file_path.exists():
        print(f"错误: 文件 {file_path} 不存在")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if args.mode == 'highlight':
        print(f"正在处理 {file_path.name}... (Highlight 模式)")
        new_content = apply_highlight(content)
        msg = "处理完成！请审查高亮部分 (==...==)，同时已自动修复公式内部空格。"
        
    elif args.mode == 'clean':
        print(f"正在清洗 {file_path.name}... (Clean 模式)")
        new_content = remove_highlight(content)
        msg = "清洗完成！已保留公式格式，且公式内部无空格。"
        
    elif args.mode == 'undo':
        print(f"正在回退 {file_path.name}... (Undo 模式)")
        new_content = undo_changes(content)
        msg = "回退完成！已撤销所有高亮处的修改。"

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(msg)

if __name__ == "__main__":
    main()