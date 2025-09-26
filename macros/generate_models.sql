{% macro generate_models() %}
    {% set model_config = fromyaml(read_file('models/model_config.yml')) %}

    {% for m in model_config['models'] %}
        {% set model_name = m['name'] %}
        {% set sql_code -%}
{{ '{{ config(' }}
materialized="{{ m.get('materialized', 'table') }}",
schema="{{ target.schema }}",
unique_key="{{ m.get('unique_key') }}"
{{ ') }}' }}

{{ '{{ ' ~ m['sql'].strip() ~ ' }}' }}
        {%- endset %}

        {{ write_file(sql_code, 'models/generated/' ~ model_name ~ '.sql') }}
        {{ log("✅ Generated model: " ~ model_name, info=True) }}
    {% endfor %}
{% endmacro %}
