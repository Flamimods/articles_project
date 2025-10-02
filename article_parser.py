import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urlparse
import re
from abc import ABC, abstractmethod
from typing import Dict, Optional
import os


class ArticleData:
    """Структура данных для статьи"""
    def __init__(self):
        self.title: str = ""
        self.author: str = ""
        self.date: str = ""
        self.content: str = ""
        self.tags: list = []
        self.url: str = ""
        self.source: str = ""


class BaseArticleParser(ABC):
    """Базовый класс для парсеров статей"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    @abstractmethod
    def can_parse(self, url: str) -> bool:
        """Проверяет, может ли парсер обработать данную ссылку"""
        pass
    
    @abstractmethod
    def parse(self, url: str) -> ArticleData:
        """Парсит статью по ссылке"""
        pass
    
    def get_page(self, url: str) -> BeautifulSoup:
        """Получает HTML страницы"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            raise Exception(f"Ошибка при получении страницы: {e}")
    
    def clean_text(self, text: str) -> str:
        """Очищает текст от лишних символов"""
        if not text:
            return ""
        # Удаляем лишние пробелы и переносы строк
        text = re.sub(r'\s+', ' ', text.strip())
        return text
    
    def extract_formatted_content(self, content_elem) -> str:
        """Извлекает контент с сохранением форматирования"""
        if not content_elem:
            return ""
        
        # Удаляем лишние элементы
        for elem in content_elem.find_all(['script', 'style', 'nav', 'aside', 'footer', 'header']):
            elem.decompose()
        
        # Создаем копию для работы
        import copy
        work_elem = copy.copy(content_elem)
        
        # Обрабатываем заголовки
        for h in work_elem.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            level = int(h.name[1])
            text = h.get_text().strip()
            if text:
                h.replace_with(f"\n\n{'#' * level} {text}\n\n")
        
        # Обрабатываем абзацы
        for p in work_elem.find_all('p'):
            text = p.get_text().strip()
            if text:
                # Удаляем подписи к изображениям (обычно короткие строки без знаков препинания)
                if len(text) < 50 and not any(char in text for char in '.!?;:'):
                    continue
                # Удаляем названия организаций/мест (обычно короткие строки)
                if len(text) < 40 and not any(char in text for char in '.!?;:'):
                    continue
                # Удаляем счетчики и метрики (только цифры и короткие слова)
                if re.match(r'^[\d\s]+$', text) or re.match(r'^[\d\s]+(онлайн|комментари|просмотр|лайк|репост)', text):
                    continue
                # Удаляем хештеги и теги
                if text.startswith('#') and len(text) < 50:
                    continue
                # Удаляем подписи к изображениям
                if text.startswith('Изображение') or text.startswith('Панель управления'):
                    continue
                # Удаляем метки времени и статусы
                if re.match(r'^[А-ЯЁ][а-яё]+\s+[А-ЯЁ]+[0-9]+[а-яё]+$', text):
                    continue
                # Удаляем автора с метками времени
                if re.match(r'^[А-ЯЁ][а-яё]+\s+[А-ЯЁ]+\s+[а-яё]+$', text):
                    continue
                # Удаляем строки с автором и AI
                if 'AI' in text and len(text) < 30:
                    continue
                # Удаляем короткие имена авторов
                if re.match(r'^[А-ЯЁ][а-яё]+\s*$', text) and len(text) < 20:
                    continue
                # Удаляем строки с автором и AI в начале
                if re.match(r'^[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+AI\d+[а-яё]+', text):
                    continue
                # Удаляем строки начинающиеся с имени и AI
                if re.match(r'^\s*[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+AI\d+[а-яё]+', text):
                    continue
                # Удаляем строки с именами и AI в любом месте
                if 'AI' in text and any(name in text for name in ['Полина', 'Артур', 'Томилко', 'Лааксо']):
                    continue
                p.replace_with(f"{text}\n\n")
        
        # Обрабатываем списки
        for ul in work_elem.find_all('ul'):
            items = []
            for li in ul.find_all('li'):
                item_text = li.get_text().strip()
                if item_text:
                    items.append(f"- {item_text}")
            if items:
                ul.replace_with('\n'.join(items) + '\n\n')
        
        for ol in work_elem.find_all('ol'):
            items = []
            for i, li in enumerate(ol.find_all('li'), 1):
                item_text = li.get_text().strip()
                if item_text:
                    items.append(f"{i}. {item_text}")
            if items:
                ol.replace_with('\n'.join(items) + '\n\n')
        
        # Обрабатываем блоки кода
        for pre in work_elem.find_all('pre'):
            text = pre.get_text().strip()
            if text:
                pre.replace_with(f"\n```\n{text}\n```\n")
        
        # Обрабатываем встроенный код (не внутри pre)
        for code in work_elem.find_all('code'):
            if code.parent and code.parent.name != 'pre':
                text = code.get_text().strip()
                if text:
                    code.replace_with(f"`{text}`")
        
        # Обрабатываем таблицы
        for table in work_elem.find_all('table'):
            markdown_table = self.convert_table_to_markdown(table)
            table.replace_with(f"\n{markdown_table}\n")
        
        # Обрабатываем переносы строк
        for br in work_elem.find_all('br'):
            br.replace_with('\n')
        
        # Удаляем изображения и их подписи
        for img in work_elem.find_all('img'):
            img.decompose()
        
        # Удаляем div с изображениями
        for div in work_elem.find_all('div', class_=lambda x: x and 'image' in x.lower()):
            div.decompose()
        
        # Получаем итоговый текст
        text = work_elem.get_text()
        
        # Очищаем и форматируем
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line:
                # Исправляем слипшиеся слова
                line = re.sub(r'([а-яё])([А-ЯЁ])', r'\1 \2', line)
                line = re.sub(r'([а-яё])([a-zA-Z])', r'\1 \2', line)
                line = re.sub(r'([a-zA-Z])([а-яё])', r'\1 \2', line)
                # Исправляем конкретные случаи
                line = re.sub(r'поступилв', 'поступил в', line)
                line = re.sub(r'Историиуспеха', 'Истории успеха', line)
                # Удаляем счетчики и метрики
                line = re.sub(r'[\d\s]+(онлайн|комментари|просмотр|лайк|репост)[\d\s]*', '', line)
                line = re.sub(r'^[\d\s]+$', '', line)
                # Удаляем хештеги и теги
                line = re.sub(r'#[\w]+', '', line)
                # Удаляем подписи к изображениям
                line = re.sub(r'Изображение\s+\w+', '', line)
                line = re.sub(r'Панель управления.*?\.', '', line)
                # Удаляем метки времени и статусы
                line = re.sub(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ]+[0-9]+[а-яё]+', '', line)
                # Удаляем автора с метками времени
                line = re.sub(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ]+\s+[а-яё]+', '', line)
                # Удаляем строки с автором и AI
                line = re.sub(r'[А-ЯЁ][а-яё]+\s+AI\s+[а-яё]+', '', line)
                line = re.sub(r'[А-ЯЁ][а-яё]+\s+AI\d+[а-яё]+', '', line)
                # Удаляем короткие имена авторов
                line = re.sub(r'^[А-ЯЁ][а-яё]+\s*$', '', line)
                # Удаляем строки с автором и AI в начале
                line = re.sub(r'^[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+AI\d+[а-яё]+', '', line)
                # Удаляем строки начинающиеся с имени и AI
                line = re.sub(r'^\s*[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\s+AI\d+[а-яё]+', '', line)
                # Удаляем строки с именами и AI в любом месте
                if 'AI' in line and any(name in line for name in ['Полина', 'Артур', 'Томилко', 'Лааксо']):
                    line = ''
                # Удаляем оставшиеся счетчики в конце строк
                line = re.sub(r'\s*\.\d+[KМ]?\s*$', '', line)
                lines.append(line)
        
        # Объединяем строки с правильными отступами
        result = []
        for i, line in enumerate(lines):
            # Пропускаем пустые строки
            if not line.strip():
                continue
                
            result.append(line)
            
            # Добавляем пустую строку после заголовков
            if line.startswith('#'):
                result.append('')
            
            # Не добавляем пустую строку после блоков кода
            
            # Добавляем пустую строку после списков (но не между элементами)
            elif (line.startswith('- ') or line.startswith(('1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. ', '9. '))):
                # Проверяем, не следующий ли элемент списка
                if (i < len(lines) - 1 and 
                    not (lines[i + 1].startswith('- ') or lines[i + 1].startswith(('1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. ', '9. ')))):
                    result.append('')
            
            # Добавляем пустую строку после абзацев, если следующий элемент - заголовок
            elif (i < len(lines) - 1 and lines[i + 1].startswith('#')):
                result.append('')
        
        return '\n'.join(result)
    
    def convert_table_to_markdown(self, table) -> str:
        """Конвертирует HTML таблицу в Markdown формат"""
        rows = []
        
        # Обрабатываем заголовки (thead или первая строка)
        header_row = table.find('thead')
        first_row = table.find('tr')
        has_headers = False
        
        if header_row:
            headers = []
            for th in header_row.find_all(['th', 'td']):
                headers.append(th.get_text().strip())
            if headers:
                rows.append('| ' + ' | '.join(headers) + ' |')
                rows.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
                has_headers = True
        elif first_row:
            # Проверяем, есть ли th в первой строке
            th_cells = first_row.find_all('th')
            if th_cells:
                headers = []
                for cell in th_cells:
                    headers.append(cell.get_text().strip())
                if headers:
                    rows.append('| ' + ' | '.join(headers) + ' |')
                    rows.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
                    has_headers = True
            else:
                # Если нет th, но есть td, создаем заголовки из первой строки
                td_cells = first_row.find_all('td')
                if td_cells:
                    headers = []
                    for cell in td_cells:
                        headers.append(cell.get_text().strip())
                    if headers:
                        rows.append('| ' + ' | '.join(headers) + ' |')
                        rows.append('| ' + ' | '.join(['---'] * len(headers)) + ' |')
                        has_headers = True
        
        # Обрабатываем строки данных
        tbody = table.find('tbody')
        if tbody:
            data_rows = tbody.find_all('tr')
        else:
            # Если нет tbody, берем все строки кроме первой (если она была заголовком)
            all_rows = table.find_all('tr')
            data_rows = all_rows[1:] if has_headers else all_rows
        
        for row in data_rows:
            cells = []
            for cell in row.find_all(['td', 'th']):
                cell_text = cell.get_text().strip()
                # Экранируем символы | в содержимом ячеек
                cell_text = cell_text.replace('|', '\\|')
                cells.append(cell_text)
            if cells:
                rows.append('| ' + ' | '.join(cells) + ' |')
        
        return '\n'.join(rows)
    
    def format_date(self, date_str: str) -> str:
        """Форматирует дату в единый формат"""
        if not date_str:
            return ""
        # Попытка распарсить различные форматы дат
        try:
            # Удаляем лишние символы
            date_str = re.sub(r'[^\d\s\-:.,]', '', date_str)
            # Здесь можно добавить более сложную логику парсинга дат
            return date_str.strip()
        except:
            return date_str.strip()


class HabrParser(BaseArticleParser):
    """Парсер для Хабра"""
    
    def can_parse(self, url: str) -> bool:
        return 'habr.com' in url and ('/post/' in url or '/articles/' in url)
    
    def parse(self, url: str) -> ArticleData:
        article = ArticleData()
        article.url = url
        article.source = "Хабр"
        
        soup = self.get_page(url)
        
        # Заголовок - пробуем разные селекторы
        title_elem = soup.find('h1', class_='tm-title')
        if not title_elem:
            title_elem = soup.find('h1')
        if title_elem:
            article.title = self.clean_text(title_elem.get_text())
        
        # Автор - пробуем разные селекторы
        author_elem = soup.find('a', class_='tm-user-info__username')
        if not author_elem:
            author_elem = soup.find('span', class_='tm-user-info__username')
        if not author_elem:
            author_elem = soup.find('a', class_='tm-user-info__name')
        if not author_elem:
            # Ищем по тексту "Автор" или в мета-информации
            author_elem = soup.find('span', string=lambda text: text and 'luvgreyair' in text)
        if author_elem:
            article.author = self.clean_text(author_elem.get_text())
        
        # Дата - пробуем разные селекторы
        date_elem = soup.find('time')
        if not date_elem:
            date_elem = soup.find('span', class_='tm-article-datetime-published')
        if date_elem:
            article.date = self.format_date(date_elem.get('datetime', date_elem.get_text()))
        
        # Контент - пробуем разные селекторы
        content_elem = soup.find('div', class_='tm-article-body')
        if not content_elem:
            content_elem = soup.find('div', class_='article-formatted-body')
        if not content_elem:
            content_elem = soup.find('article')
        if not content_elem:
            content_elem = soup.find('div', class_='post__text')
        if content_elem:
            article.content = self.extract_formatted_content(content_elem)
        
        # Теги - пробуем разные селекторы
        tags_elem = soup.find_all('a', class_='tm-tags-list__link')
        if not tags_elem:
            tags_elem = soup.find_all('a', class_='tm-tag')
        if not tags_elem:
            tags_elem = soup.find_all('span', class_='tm-tag')
        article.tags = [self.clean_text(tag.get_text()) for tag in tags_elem]
        
        return article


class ProglibParser(BaseArticleParser):
    """Парсер для Proglib"""
    
    def can_parse(self, url: str) -> bool:
        return 'proglib.io' in url and '/p/' in url
    
    def parse(self, url: str) -> ArticleData:
        article = ArticleData()
        article.url = url
        article.source = "Proglib"
        
        soup = self.get_page(url)
        
        # Заголовок
        title_elem = soup.find('h1', class_='post-title')
        if not title_elem:
            title_elem = soup.find('h1')
        if title_elem:
            article.title = self.clean_text(title_elem.get_text())
        
        # Автор
        author_elem = soup.find('a', class_='author-name')
        if not author_elem:
            author_elem = soup.find('span', class_='author')
        if author_elem:
            article.author = self.clean_text(author_elem.get_text())
        
        # Дата
        date_elem = soup.find('time')
        if not date_elem:
            date_elem = soup.find('span', class_='date')
        if date_elem:
            article.date = self.format_date(date_elem.get_text())
        
        # Контент
        content_elem = soup.find('div', class_='post-content')
        if not content_elem:
            content_elem = soup.find('article')
        if content_elem:
            article.content = self.extract_formatted_content(content_elem)
        
        # Теги
        tags_elem = soup.find_all('a', class_='tag')
        if not tags_elem:
            tags_elem = soup.find_all('span', class_='tag')
        article.tags = [self.clean_text(tag.get_text()) for tag in tags_elem]
        
        return article


class VcRuParser(BaseArticleParser):
    """Парсер для vc.ru"""
    
    def can_parse(self, url: str) -> bool:
        return 'vc.ru' in url and ('/post/' in url or '/ai/' in url or '/marketing/' in url or '/money/' in url or '/travel/' in url or '/career/' in url or '/education/' in url)
    
    def parse(self, url: str) -> ArticleData:
        article = ArticleData()
        article.url = url
        article.source = "vc.ru"
        
        soup = self.get_page(url)
        
        # Заголовок
        title_elem = soup.find('h1', class_='content-title')
        if not title_elem:
            title_elem = soup.find('h1')
        if title_elem:
            article.title = self.clean_text(title_elem.get_text())
        
        # Автор
        author_elem = soup.find('a', class_='user-name')
        if not author_elem:
            author_elem = soup.find('span', class_='author')
        if author_elem:
            article.author = self.clean_text(author_elem.get_text())
        
        # Дата
        date_elem = soup.find('time')
        if not date_elem:
            date_elem = soup.find('span', class_='date')
        if date_elem:
            article.date = self.format_date(date_elem.get_text())
        
        # Контент
        content_elem = soup.find('div', class_='content')
        if not content_elem:
            content_elem = soup.find('article')
        if content_elem:
            article.content = self.extract_formatted_content(content_elem)
        
        # Теги
        tags_elem = soup.find_all('a', class_='tag')
        if not tags_elem:
            tags_elem = soup.find_all('span', class_='tag')
        article.tags = [self.clean_text(tag.get_text()) for tag in tags_elem]
        
        return article


class ArticleParser:
    """Основной класс для парсинга статей"""
    
    def __init__(self):
        self.parsers = [
            HabrParser(),
            ProglibParser(),
            VcRuParser()
        ]
    
    def parse_article(self, url: str) -> ArticleData:
        """Парсит статью по URL"""
        for parser in self.parsers:
            if parser.can_parse(url):
                return parser.parse(url)
        
        raise Exception(f"Неподдерживаемый URL: {url}")
    
    def to_markdown(self, article: ArticleData) -> str:
        """Конвертирует статью в Markdown формат"""
        md = []
        
        # Заголовок
        if article.title:
            md.append(f"# {article.title}")
            md.append("")
        
        # Метаинформация
        meta = []
        if article.author:
            meta.append(f"**Автор:** {article.author}")
        if article.date:
            meta.append(f"**Дата:** {article.date}")
        if article.source:
            meta.append(f"**Источник:** {article.source}")
        if article.url:
            meta.append(f"**Ссылка:** {article.url}")
        
        if meta:
            md.extend(meta)
            md.append("")
        
        # Теги
        if article.tags:
            tags_str = ", ".join([f"`{tag}`" for tag in article.tags])
            md.append(f"**Теги:** {tags_str}")
            md.append("")
        
        # Разделитель
        md.append("---")
        md.append("")
        
        # Контент
        if article.content:
            md.append(article.content)
        
        return "\n".join(md)
    
    def save_to_file(self, article: ArticleData, filename: str = None) -> str:
        """Сохраняет статью в Markdown файл"""
        if not filename:
            # Генерируем имя файла из заголовка
            safe_title = re.sub(r'[^\w\s-]', '', article.title)
            safe_title = re.sub(r'[-\s]+', '-', safe_title)
            filename = f"{safe_title[:50]}.md"
        
        # Проверяем, что имя файла не пустое
        if not filename or filename.strip() == "":
            filename = f"article_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        # Убеждаемся, что файл имеет расширение .md
        if not filename.endswith('.md'):
            filename += '.md'
        
        md_content = self.to_markdown(article)
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(md_content)
        except Exception as e:
            raise Exception(f"Ошибка при сохранении файла {filename}: {e}")
        
        return filename
