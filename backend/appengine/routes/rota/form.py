# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from config.template_middleware import TemplateResponse
from gaecookie.decorator import no_csrf
from gaepermission.decorator import login_not_required, permissions
from permission_app.model import ADMIN, GERENTE
from tekton import router

@permissions(GERENTE,ADMIN)
@no_csrf
def index():
    contexto = {'save_path': router.to_path(salvar)}
    return TemplateResponse(contexto)


@login_not_required
def salvar(_resp, nome):
    _resp.write(nome)
