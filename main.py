from dataclasses import dataclass, field
from bs4 import BeautifulSoup
from lxml import etree
import requests
from fake_useragent import UserAgent
from sqlalchemy import create_engine, Integer, String, Column, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base


# Ниже код для настройки SQlalchemy, чтобы сохранить данный в БД
engine = create_engine(('sqlite:///data.db'))
Base = declarative_base()
Session = sessionmaker(autoflush=False, bind=engine)
session_sql = Session()


# Создаю таблицы для добавления данных в БД
# Создано 4 таблицы для сохранения данных профиля и 3 для сохранения данных о продукте
class ProfileData(Base):
    __tablename__ = 'profile'
    id = Column(Integer, primary_key=True)
    name = Column(String(25))
    surname = Column(String(25))
    email = Column(String(25))
    city = Column(String(100))


class ProductData(Base):
    __tablename__ = 'product'
    id = Column(Integer, primary_key=True)
    title = Column(String(250))
    price_opt = Column(String(15))
    price_roz = Column(String(15))
    feedback_num = Column(String(15))
    store_list = relationship('StoreData', backref='product', lazy='dynamic')
    discussion_list = relationship('FeedbackData', backref='product', lazy='dynamic')


class StoreData(Base):
    __tablename__ = 'store'
    id = Column(Integer, primary_key=True)
    store = Column(String(250))
    product_id = Column(Integer, ForeignKey('product.id'))


class FeedbackData(Base):
    __tablename__ = 'feedback'
    id = Column(Integer, primary_key=True)
    post = Column(String(250))
    product_id = Column(Integer, ForeignKey('product.id'))


Base.metadata.create_all(bind=engine)


ua = UserAgent() #Создал переменную для фейкового User-Agent
HEADERS = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "user-agent": ua.random,
    }
# Ссылки для авторизации и перехода в избранное
PROFILE_URL = "https://siriust.ru/profiles-update/"
WISHLIST_URL = "https://siriust.ru/wishlist/"

#Данные решил сохранять в структуре словаря, для этого использовал dataclass
@dataclass
class Profile:
    name: str
    surname: str
    email: str
    city: str

    def __repr__(self):
        return f"{self.__dict__}"


@dataclass
class Product:
    title: str
    price_opt: str
    price_roz: str
    feedback_num: str
    store_list: list = field(default_factory=list)
    discussion_list: list = field(default_factory=list)

    def __repr__(self):
        return f"{self.__dict__}"


def post_login() -> object:
    """
    Функция отправляет запрос на сайт для прохождения авторизации и записи сессии авторизованного пользователя
    :return: возвращает объект сессии для дальнейшего использования в запросах
    """
    url = "https://siriust.ru/"

    data = {
        "return_url": "index.php",
        "redirect_url": "index.php",
        "user_login": input("Введите логин: "),
        "password": input("Ввдите пароль: "),
        "dispatch[auth.login]": "",
    }
    session = requests.Session()
    session.headers.update(HEADERS)
    res = session.post(url, data=data, headers=HEADERS, timeout=15)
    if res.status_code == 200:
        print(f"The user is logged in")
    return session


def write_file(session: object, url: str):
    """
    Функция сохраняет страницы профиля и избранного товара в файл, чтобы часто не загружать сервер запросами
    и показать один из способов парсинга
    :param session: объект ссесии
    :param url: ссылка на страницу
    """
    get_data = session.get(url, headers=HEADERS, cookies=session.cookies)
    try:
        if url == PROFILE_URL:
            with open('data/profile.html', 'w', encoding='utf-8') as prof_file:
                prof_file.write(get_data.text)
        elif url == WISHLIST_URL:
            with open("data/wish.html", "w", encoding="utf-8") as wish:
                src = wish.write(get_data.text)
    except Exception as ex:
        print(f"The file is not written, check the correct path, {ex}")


def get_data_profile() -> Profile:
    """
    Функция читает файл с html кодом и собирает данные по профилю пользователя
    данные записываются в объект датакласса Profile
    :return: объект
    """
    try:
        with open('data/profile.html', 'r', encoding='utf-8') as prof_file:
            src = prof_file.read()
    except Exception as ex:
        print(f"File not read, {ex}")

    soup = BeautifulSoup(src, "lxml")
    email = soup.find("input", id='email').get("value")
    name = soup.find("input", id='elm_15').get("value")
    surname = soup.find("input", id='elm_17').get("value")
    city = soup.find("input", id="elm_23").get("value")
    user_prof = Profile(name, surname, email, city)
    return user_prof


def get_links_product() -> list:
    """
    Функция собирает все ссылки на товары в избранном
    :return: список ссылок
    """
    links_prod = []
    try:
        with open('data/wish.html', 'r', encoding='utf-8') as wishlist:
            src = wishlist.read()
    except Exception as ex:
        print(f"File not read, {ex}")

    soup = BeautifulSoup(src, 'lxml')
    products = soup.find_all("a", class_="product-title")
    for link in products:
        link_product = link.get('href')
        links_prod.append(link_product)
    return links_prod


def get_data_product(session: object, list_links: list) -> list[Product]:
    """
    Функция проходит по списку ссылок продуктов в избранном и парсит данные, складывая в объект Product
    :param session: сессия авторизованного пользователя
    :param list_links: список ссылок
    :return: список объектов Product
    """
    list_prod = []
    for url in list_links:
        request = session.get(url, headers=HEADERS, cookies=session.cookies)
        soup = BeautifulSoup(request.text, "lxml")
        title = soup.find("h1", class_="ty-product-block-title").text.strip()
        price_opt = etree.HTML(str(soup)).xpath(
            '//*[@class="ty-product-block__price-actual"]/span/span/bdi/span')[0].text.replace("\xa0", "")
        price_roz = etree.HTML(str(soup)).xpath(
            '//*[@class="ty-product-block__price-second"]/span/bdi/span')[0].text.replace("\xa0", "")
        feedback = soup.find("a", class_="ty-discussion__review-a cm-external-click")

        if feedback == None:
            feedback_num = "Отзывов нет"
        else:
            feedback_num = str(feedback.text[0])
        product = Product(title, price_opt, price_roz, feedback_num)
        find_store = soup.find_all("div", class_="ty-product-feature")
        for store in find_store[1::]:
            in_stock = store.div.get_text()
            in_stock = in_stock.translate({ord(i): None for i in " —"}).strip()
            if in_stock != 'отсутствует':
                start = store.text.find("г")
                end = store.text.find(":")
                product.store_list.append(store.text[start:end])
        discussions = soup.find_all('div', class_="ty-discussion-post__content ty-mb-l")
        for post in discussions:
            post_in = post.find("div", class_="ty-discussion-post__message").text
            product.discussion_list.append(post_in)
        list_prod.append(product)
    return list_prod


def add_profile(profile: Profile):
    """
    Функция добавляет данные пользователя в БД в файл data.db
    :param profile: объект Profile
    """
    try:
        session_sql.add(ProfileData(name=profile.name,
                                    surname=profile.surname,
                                    email=profile.email,
                                    city=profile.city))
        session_sql.commit()
        session_sql.close()
    except Exception as ex:
        session_sql.rollback()
        raise ex


def add_product(product: list[Product]):
    """
    Функция добавляет информацию по продуктам в таблицы product, store, feedback
    таблицы связаны один ко многим
    :param product: список объектов Product
    """
    try:
        for item in product:
            session_sql.add(ProductData(title=item.title,
                                        price_opt=item.price_opt,
                                        price_roz=item.price_roz,
                                        feedback_num=item.feedback_num,))
            session_sql.commit()

            prod_id = session_sql.query(ProductData.id).where(ProductData.title == item.title)
            for store in item.store_list:
                session_sql.add(StoreData(store=store,
                                          product_id=prod_id))
            for post in item.discussion_list:
                session_sql.add(FeedbackData(post=post,
                                             product_id=prod_id))
            session_sql.commit()
            session_sql.close()
    except Exception as ex:
        session_sql.rollback()
        raise ex


def main():
    session = post_login()
    write_file(session, PROFILE_URL)
    write_file(session, WISHLIST_URL)
    profile = get_data_profile()
    links = get_links_product()
    prod = get_data_product(session, links)
    add_profile(profile)
    add_product(prod)


if __name__ == '__main__':
    main()
