#!/usr/bin/env python3
"""
Программа для парсинга статей с Хабра, Proglib и vc.ru в единый Markdown формат
"""

import sys
import argparse
from urllib.parse import urlparse
from article_parser import ArticleParser


def main():
    parser = argparse.ArgumentParser(
        description='Парсинг статей с Хабра, Proglib и vc.ru в Markdown формат'
    )
    parser.add_argument('url', help='URL статьи для парсинга')
    parser.add_argument('-o', '--output', help='Имя выходного файла (по умолчанию генерируется автоматически)')
    parser.add_argument('-p', '--print', action='store_true', help='Вывести результат в консоль')
    
    args = parser.parse_args()
    
    # Валидация URL
    try:
        parsed_url = urlparse(args.url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError("Некорректный URL")
    except Exception as e:
        print(f"Ошибка валидации URL: {e}")
        sys.exit(1)
    
    try:
        # Создаем парсер
        article_parser = ArticleParser()
        
        print(f"Парсинг статьи: {args.url}")
        print("Ожидайте...")
        
        # Парсим статью
        article = article_parser.parse_article(args.url)
        
        if not article.title:
            print("Предупреждение: Не удалось извлечь заголовок статьи")
        
        if not article.content:
            print("Ошибка: Не удалось извлечь содержимое статьи")
            sys.exit(1)
        
        # Выводим результат в консоль, если запрошено
        if args.print:
            print("\n" + "="*50)
            print(article_parser.to_markdown(article))
            print("="*50)
        
        # Сохраняем в файл
        filename = article_parser.save_to_file(article, args.output)
        print(f"Статья сохранена в файл: {filename}")
        
        # Выводим краткую информацию
        print(f"\nЗаголовок: {article.title}")
        print(f"Автор: {article.author}")
        print(f"Источник: {article.source}")
        if article.tags:
            print(f"Теги: {', '.join(article.tags)}")
        
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
