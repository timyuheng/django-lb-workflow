from django.core.exceptions import ImproperlyConfigured
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic.base import TemplateResponseMixin
from django.views.generic.base import View
from django.views.generic.list import MultipleObjectMixin
from lbutils import do_filter
from lbutils import simple_export2xlsx

from lbworkflow.models import Process

from .helper import user_wf_info_as_dict
from .mixin import FormsView
from .mixin import ModelFormsMixin


class ProcessTemplateResponseMixin(TemplateResponseMixin):
    def get_template_names(self):
        try:
            return super(ProcessTemplateResponseMixin, self).get_template_names()
        except ImproperlyConfigured:
            base_tmpl = self.base_template_name
            templates = ["%s/%s" % (self.wf_code, base_tmpl,), ]
            _meta = None
            object = getattr(self, 'object', None)
            if object:
                _meta = self.object._meta
            elif self.model:
                _meta = self.model._meta
            if _meta:
                app_label = _meta.app_label
                object_name = _meta.object_name.lower()
                templates.extend([
                    "%s/%s/%s" % (app_label, object_name, base_tmpl,),
                    "%s/%s" % (app_label, base_tmpl,), ])
            return templates


class ExcelResponseMixin(object):
    titles = [
    ]
    file_name = ''

    def get_data(self, o):
        return []

    def get_file_name(self):
        return self.file_name

    def render_to_excel(self, object_list, **kwargs):
        return simple_export2xlsx(
            self.get_file_name(), self.titles,
            object_list, lambda o: self.get_data(o))


class CreateView(ModelFormsMixin, ProcessTemplateResponseMixin, FormsView):
    form_classes = {
        # 'main_form': None,
    }
    wf_code = None
    model = None
    base_template_name = 'form.html'

    def get_success_url(self):
        return reverse('wf_detail', pk=self.object.pinstance.pk)

    def get_context_data(self, **kwargs):
        kwargs['wf_code'] = self.wf_code
        kwargs['process'] = get_object_or_404(Process, code=self.wf_code)
        return kwargs

    def forms_valid(self, **forms):
        form = forms.pop('main_form')
        self.object = form.save_new_process(self.request, self.wf_code)
        # TODO forms.save
        return HttpResponseRedirect(self.get_success_url())

    def dispatch(self, request, wf_code, *args, **kwargs):
        self.request = request
        self.wf_code = wf_code
        return super(CreateView, self).dispatch(request, *args, **kwargs)


class UpdateView(ModelFormsMixin, ProcessTemplateResponseMixin, FormsView):
    form_classes = {
        # 'main_form': None,
    }
    wf_code = None
    model = None
    base_template_name = 'form.html'

    def get_success_url(self):
        return reverse('wf_detail', pk=self.object.pinstance.pk)

    def get_context_data(self, **kwargs):
        kwargs.update(user_wf_info_as_dict(self.object, self.request.user))
        return kwargs

    def forms_valid(self, **forms):
        form = forms.pop('main_form')
        self.object = form.update_process(self.request, self.wf_code)
        # TODO forms.save
        return HttpResponseRedirect(self.get_success_url())

    def dispatch(self, request, wf_object, *args, **kwargs):
        self.request = request
        self.object = wf_object
        return super(UpdateView, self).dispatch(request, *args, **kwargs)


class ListView(ExcelResponseMixin, ProcessTemplateResponseMixin, MultipleObjectMixin, View):
    search_form_class = None
    quick_query_fields = []
    int_quick_query_fields = []
    ordering = '-pk'
    base_template_name = 'list.html'

    def dispatch(self, request, *args, wf_code=None, **kwargs):
        self.request = request
        self.wf_code = wf_code
        return super(ListView, self).dispatch(request, *args, **kwargs)

    def get_quick_query_fields(self):
        fields = [
            'pinstance__no',
            'pinstance__summary',
            'pinstance__created_by__username',
        ]
        fields.extend(self.quick_query_fields)
        return fields

    def get_base_queryset(self, query_data):
        # qs = get_can_view_wf(model, request.user, wf_code, ext_param_process=__ext_param_process)
        from django.contrib.auth.models import User
        qs = User.objects.all()
        quick_query_fields = self.get_quick_query_fields()
        qs = do_filter(qs, query_data, quick_query_fields, self.int_quick_query_fields)
        return qs

    def get_search_form(self, request):
        if not self.search_form_class:
            return None
        search_form = self.search_form_class(request.GET)
        if not search_form.is_valid():
            pass
        return search_form

    def get(self, request, *args, **kwargs):
        search_form = self.get_search_form(request)
        self.queryset = self.get_base_queryset(
            search_form.cleaned_data if search_form else None)
        self.object_list = self.get_queryset()

        if request.GET.get('export'):
            return self.render_to_excel(self.object_list)

        process = None
        if self.wf_code:
            process = get_object_or_404(Process, code=self.wf_code)
        context = self.get_context_data(
            search_form=search_form, process=process)
        return self.render_to_response(context)