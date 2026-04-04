"""CLI интерфейс для Agent Scout."""

import asyncio
import csv
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()

from agent_scout.config import load_config
from agent_scout.orchestrator import Orchestrator

console = Console()


def run_async(coro):
    """Запустить async-функцию из синхронного контекста."""
    return asyncio.get_event_loop().run_until_complete(coro)


@click.group()
@click.option("--config", "-c", default="config.yaml", help="Путь к config.yaml")
@click.pass_context
def cli(ctx, config):
    """Agent Scout — конкурентная разведка для строительных услуг."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config


@cli.command()
@click.option("--platform", "-p", default="avito", help="Площадка (avito)")
@click.option("--niche", "-n", required=True, help="Ниша / поисковый запрос")
@click.option("--location", "-l", required=True, help="Город")
@click.option("--limit", default=20, help="Максимум объявлений")
@click.pass_context
def scrape(ctx, platform, niche, location, limit):
    """Скрапинг объявлений с площадки."""
    config = load_config(ctx.obj["config_path"])
    orch = Orchestrator(config)

    async def _run():
        await orch.init()
        try:
            count = await orch.scrape(platform, niche, location, limit)
            console.print(f"[green]Сохранено {count} объявлений[/green]")
        finally:
            await orch.close()

    run_async(_run())


@cli.command()
@click.option("--platform", "-p", default="avito", help="Площадка")
@click.option("--limit", default=10, help="Максимум профилей")
@click.pass_context
def enrich(ctx, platform, limit):
    """Обогатить профили продавцов (рейтинги, отзывы)."""
    config = load_config(ctx.obj["config_path"])
    orch = Orchestrator(config)

    async def _run():
        await orch.init()
        try:
            count = await orch.enrich_profiles(platform, limit)
            console.print(f"[green]Обогащено {count} профилей[/green]")
        finally:
            await orch.close()

    run_async(_run())


@cli.group()
def messages():
    """Управление сообщениями."""
    pass


@messages.command("check")
@click.option("--platform", "-p", default="avito", help="Площадка")
@click.pass_context
def messages_check(ctx, platform):
    """Проверить новые ответы и ответить через AI."""
    config = load_config(ctx.obj["config_path"])
    orch = Orchestrator(config)

    async def _run():
        await orch.init()
        try:
            count = await orch.check_replies(platform)
            console.print(f"[green]Отправлено {count} ответов[/green]")
        finally:
            await orch.close()

    run_async(_run())


@messages.command("send")
@click.option("--platform", "-p", default="avito", help="Площадка")
@click.option("--goal", "-g", default="Узнать цены на мех. штукатурку ~40м2 стен, ЖК Парксайд, Москва", help="Цель переписки")
@click.option("--limit", default=None, type=int, help="Максимум сообщений")
@click.pass_context
def messages_send(ctx, platform, goal, limit):
    """Отправить первые сообщения продавцам."""
    config = load_config(ctx.obj["config_path"])
    orch = Orchestrator(config)

    async def _run():
        await orch.init()
        try:
            count = await orch.send_messages(platform, goal, limit)
            console.print(f"[green]Отправлено {count} первых сообщений[/green]")
        finally:
            await orch.close()

    run_async(_run())


@cli.command("export")
@click.option("--format", "fmt", type=click.Choice(["csv", "json"]), default="csv")
@click.option("--output", "-o", default="export", help="Имя файла (без расширения)")
@click.pass_context
def export_data(ctx, fmt, output):
    """Экспорт собранных данных."""
    from agent_scout.database.repository import Repository

    config = load_config(ctx.obj["config_path"])
    repo = Repository(config.database.path)

    async def _run():
        await repo.init_db()
        sellers = await repo.list_sellers()
        listings = await repo.list_listings()

        if fmt == "csv":
            # Экспорт продавцов
            sellers_file = f"{output}_sellers.csv"
            with open(sellers_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ID", "Платформа", "Имя", "Рейтинг", "Отзывы",
                    "Дата регистрации", "Объявлений", "URL профиля",
                ])
                for s in sellers:
                    writer.writerow([
                        s.id, s.platform, s.name, s.rating, s.reviews_count,
                        s.registration_date, s.listings_count, s.profile_url,
                    ])
            console.print(f"[green]Продавцы: {sellers_file} ({len(sellers)} записей)[/green]")

            # Экспорт объявлений
            listings_file = f"{output}_listings.csv"
            with open(listings_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "ID", "Продавец ID", "Платформа", "Название",
                    "Цена", "Категория", "Локация", "URL",
                ])
                for l in listings:
                    writer.writerow([
                        l.id, l.seller_id, l.platform, l.title,
                        l.price, l.category, l.location, l.url,
                    ])
            console.print(f"[green]Объявления: {listings_file} ({len(listings)} записей)[/green]")

        await repo.close()

    run_async(_run())


@cli.command("run")
@click.pass_context
def run_auto(ctx):
    """Запустить полный автоматический цикл."""
    config = load_config(ctx.obj["config_path"])
    orch = Orchestrator(config)

    console.print("[bold]Запуск автоматического цикла...[/bold]")
    console.print("Расписание имитирует поведение живого человека.")
    console.print("Нажмите Ctrl+C для остановки.\n")

    try:
        run_async(orch.run_auto())
    except KeyboardInterrupt:
        console.print("\n[yellow]Остановка по Ctrl+C[/yellow]")
        run_async(orch.close())


@cli.command("status")
@click.pass_context
def status(ctx):
    """Показать статистику собранных данных."""
    from agent_scout.database.repository import Repository

    config = load_config(ctx.obj["config_path"])
    repo = Repository(config.database.path)

    async def _run():
        await repo.init_db()

        sellers = await repo.list_sellers()
        listings = await repo.list_listings()
        conversations = await repo.get_active_conversations()

        table = Table(title="Agent Scout — Статус")
        table.add_column("Метрика", style="bold")
        table.add_column("Значение", justify="right")

        table.add_row("Продавцов в БД", str(len(sellers)))
        table.add_row("Объявлений в БД", str(len(listings)))
        table.add_row("Активных диалогов", str(len(conversations)))

        # По платформам
        platforms = {}
        for s in sellers:
            platforms[s.platform] = platforms.get(s.platform, 0) + 1
        for p, c in platforms.items():
            table.add_row(f"  {p}: продавцов", str(c))

        console.print(table)
        await repo.close()

    run_async(_run())


if __name__ == "__main__":
    cli()
