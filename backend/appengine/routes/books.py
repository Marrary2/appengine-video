# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from google.appengine.ext import ndb

from config.template_middleware import TemplateResponse
from gaebusiness.business import Command, CommandParallel, CommandExecutionException, CommandSequential
from gaecookie.decorator import no_csrf
from gaeforms.ndb.form import ModelForm
from gaegraph.model import Node, Arc, to_node_key
from tekton import router
from tekton.gae.middleware.redirect import RedirectResponse

# Handlers

@no_csrf
def index(_logged_user):
    chave_do_usuario = _logged_user.key
    query = AutorArco.query(AutorArco.origin == chave_do_usuario)
    autor_arcos = query.fetch()
    chaves_de_livros = [arco.destination for arco in autor_arcos]
    livro_lista = ndb.get_multi(chaves_de_livros)
    book_form = BookFormTable()
    livro_lista = [book_form.fill_with_model(livro) for livro in livro_lista]
    editar_form_path = router.to_path(editar_form)
    delete_path = router.to_path(delete)
    for livro in livro_lista:
        livro['edit_path'] = '%s/%s' % (editar_form_path, livro['id'])
        livro['delete_path'] = '%s/%s' % (delete_path, livro['id'])
    contexto = {'livro_lista': livro_lista,
                'form_path': router.to_path(form)}
    return TemplateResponse(contexto)


@no_csrf
def editar_form(book_id):
    book_id = int(book_id)
    book = Book.get_by_id(book_id)
    book_form = BookForm()
    book_form.fill_with_model(book)
    contexto = {'salvar_path': router.to_path(editar, book_id),
                'book': book_form}
    return TemplateResponse(contexto, 'books/form.html')


def editar(book_id, **propriedades):
    book_id = int(book_id)
    book = Book.get_by_id(book_id)
    book_form = BookForm(**propriedades)
    erros = book_form.validate()
    if erros:
        contexto = {'salvar_path': router.to_path(salvar),
                    'erros': erros,
                    'book': book_form}
        return TemplateResponse(contexto, 'books/form.html')
    else:
        book_form.fill_model(book)
        book.put()
        return RedirectResponse(router.to_path(index))


@no_csrf
def form():
    contexto = {'salvar_path': router.to_path(salvar)}
    return TemplateResponse(contexto)


def delete(book_id):
    apagar_cmd = ApagarLivro(book_id)
    apagar_arcos = ApagarAutorArcos(book_id)
    comandos_paralelos = CommandParallel(apagar_cmd, apagar_arcos)
    comandos_paralelos()
    return RedirectResponse(router.to_path(index))


def salvar(_logged_user, **propriedades):
    salvar_livro_com_autor_cmd = SalvarLivroComAutor(_logged_user,**propriedades)
    try:
        salvar_livro_com_autor_cmd()
        return RedirectResponse(router.to_path(index))
    except CommandExecutionException:
        contexto = {'salvar_path': router.to_path(salvar),
                    'erros': salvar_livro_com_autor_cmd.errors,
                    'book': propriedades}
        return TemplateResponse(contexto, 'books/form.html')


# Modelos
class Book(Node):
    title = ndb.StringProperty(required=True)
    price = ndb.FloatProperty()

    release = ndb.DateProperty()


class AutorArco(Arc):
    origin = ndb.KeyProperty(required=True)
    destination = ndb.KeyProperty(Book, required=True)


# Formulários


class BookFormTable(ModelForm):
    _model_class = Book
    _include = [Book.title, Book.creation, Book.price]


class BookForm(ModelForm):
    _model_class = Book
    _include = [Book.title, Book.release, Book.price]


# Comandos

class SalvarLivroComAutor(CommandSequential):
    def __init__(self, autor, **propriedades_do_livro):
        salvar_livro_cmd = SalvarLivro(**propriedades_do_livro)
        salvar_autor_cmd = SalvarAutor(autor)
        super(SalvarLivroComAutor, self).__init__(salvar_livro_cmd, salvar_autor_cmd)


class SalvarAutor(Command):
    def __init__(self, autor, livro=None):
        super(SalvarAutor, self).__init__()
        self.autor = to_node_key(autor)
        self.livro = livro and to_node_key(livro)

    def do_business(self):
        self.result = AutorArco(origin=self.autor, destination=self.livro)
        self._to_commit = self.result

    def handle_previous(self, command):
        self.livro = command.result


class SalvarLivro(Command):
    def __init__(self, **propriedades):
        super(SalvarLivro, self).__init__()
        self.form = BookForm(**propriedades)

    def do_business(self):
        erros = self.form.validate()
        self.errors = erros
        if not erros:
            self._to_commit = self.form.fill_model()
            self.result = self._to_commit


class ApagarLivro(Command):
    def __init__(self, livro_id):
        super(ApagarLivro, self).__init__()
        self.livro_key = ndb.Key(Book, int(livro_id))
        self.futuro = None

    def set_up(self):
        self.futuro = self.livro_key.delete_async()

    def do_business(self):
        self.futuro.get_result()


class ApagarAutorArcos(Command):
    def __init__(self, livro_id):
        super(ApagarAutorArcos, self).__init__()
        chave_do_livro = ndb.Key(Book, int(livro_id))
        self.query = AutorArco.find_origins(chave_do_livro)
        self.futuro = None

    def set_up(self):
        self.futuro = self.query.fetch_async(keys_only=True)

    def do_business(self):
        chaves_dos_arcos = self.futuro.get_result()
        ndb.delete_multi(chaves_dos_arcos)
