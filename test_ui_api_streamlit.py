"""La app usa width="stretch"/"content" (use_container_width quedó obsoleto en Streamlit)."""
import pytest

st = pytest.importorskip("streamlit")
pd = pytest.importorskip("pandas")


@pytest.mark.parametrize("ancho", ["stretch", "content"])
def test_widgets_aceptan_width(ancho):
    st.button("x", width=ancho, key=f"b_{ancho}")
    st.download_button("x", b"1", file_name="x.txt", width=ancho, key=f"d_{ancho}")
    st.dataframe(pd.DataFrame({"a": [1]}), width=ancho)
    st.line_chart(pd.DataFrame({"a": [1, 2]}), width=ancho)


def test_plotly_chart_acepta_width():
    go = pytest.importorskip("plotly.graph_objects")
    st.plotly_chart(go.Figure(), width="stretch")
