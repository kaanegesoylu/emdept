"""Yöntem sayfası: formüller, varsayımlar, kaynaklar."""
import streamlit as st


def render() -> None:
    st.title("Yöntem")
    st.caption("Panelin hesapladığı her sayının nereden geldiği.")
    st.markdown(r"""
**1. Yoğunluk.** Her saat dilimi *h* için, seçili günlerde o saatte kaydı yapılan hasta sayılarının ortalaması geliş hızıdır (λₕ, hasta/saat). Hizmet hızı μ = 60 / ortalama muayene süresi (dk).

$$\rho_h = \frac{\lambda_h}{c_h\,\mu} \qquad \rho \ge 1 \Rightarrow \text{kuyruk sınırsız büyür}$$

**2. Dağılım kontrolü.** Poisson gelişlerde varyans ortalamaya eşittir. Her saat dilimi için D = s² / x̄ ve (n−1)·D ~ χ²(n−1) ile iki yönlü test yapılır. Tüm saatler tek havuzda incelenirse gün içi değişim D'yi yapay olarak büyütür; kontrol bu yüzden saat bazındadır. Muayene süresinde CV ≈ 1 üstel dağılımla uyumludur.

**3. Bekleme süresi (M/M/c, Erlang C).**

$$a=\frac{\lambda}{\mu},\quad W_q=\frac{C(c,a)}{c\mu-\lambda},\quad P(W_q\le t)=1-C(c,a)\,e^{-(c\mu-\lambda)t}$$

C(c, a), Erlang B özyinelemesiyle sayısal olarak kararlı biçimde hesaplanır. M/G/c seçilirse Allen–Cunneen yaklaşımı: W_q ≈ W_q(M/M/c)·(1 + CV²)/2.

**4. Saatlik yöntem.** SIPP her saati kendi λ değeriyle bağımsız ve kararlı kabul eder. Lag-SIPP geliş eğrisini ortalama hizmet süresi kadar geciktirir (Green ve ark., 2006).

**5. Karar.** Her saat için hedefi sağlayan en küçük *c* aranır.

**6. Doğrulama.** Veride muayeneye alınma saati varsa gerçek bekleme (alınma − kayıt) modelle karşılaştırılır. Ayrık olay simülasyonu ilk gelen ilk hizmet alır kuralıyla, saat saat değişen hekim sayısıyla çalışır.
""")
    with st.expander("Varsayımlar ve sınırlar"):
        st.markdown("""
- Yeşil alan içinde öncelik yoktur; sıra ilk gelen ilk hizmet alır.
- Erlang C hastaların sonsuz sabırlı olduğunu varsayar. Muayene olmadan ayrılan oranı yüksekse Erlang A (M/M/c+M) daha uygun olabilir.
- “Çıkış − muayeneye alınma” tetkik ve tedavi beklemesini de içerir; hekim süresi olarak kullanılırsa gereken hekim sayısı olduğundan yüksek çıkar.
- Hekimlerin tüm zamanını yeşil alana ayırdığı varsayılır.
""")
    with st.expander("Kaynaklar"):
        st.markdown("""
1. Green L.V., Soares J., Giglio J.F., Green R.A., “Using queueing theory to increase the effectiveness of emergency department provider staffing”, *Academic Emergency Medicine*, vol. 13, pp. 61–68, 2006.
2. Yom-Tov G.B., Mandelbaum A., *Manufacturing & Service Operations Management*, vol. 16(2), pp. 283–299, 2014. doi:10.1287/msom.2013.0474
3. Little J.D.C., “A proof for the queuing formula L = λW”, *Operations Research*, vol. 9(3), pp. 383–387, 1961.
4. Kuo Y.H., Chan N.B., Leung J.M.Y., Meng H., So A.M.C., Tsoi K.K.F., Graham C.A., “An integrated approach of machine learning and systems thinking for waiting time prediction in an emergency department”, *International Journal of Medical Informatics*, vol. 139, 104143, 2020.
5. Durmuş (2009), Uludağ Üniversitesi tezi: yoğunluk 16–24 saatleri arasında (sentetik “akşam yoğun” profilinin dayanağı).
6. 6698 sayılı Kişisel Verilerin Korunması Kanunu, md. 28/1-(b).
""")
