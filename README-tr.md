# diyanet-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/diyanet-mcp

**Diyanet namaz vakitleri** (namazvakitleri.diyanet.gov.tr) için resmi olmayan, **salt okunur** MCP sunucusu — Diyanet İşleri Başkanlığı'nın Türkiye için yayımladığı **resmi vakit çizelgesi**: **81 il ve ilçeleri** için bugünün 6 namaz vakti, Miladi + Hicri tarihli yıllık tablo ve her yer için kıble açısı/saati ile astronomik gün doğumu/batımı.

> "Turkey MCP factory" projesinin parçasıdır. Diyanet ile bağlantısı yoktur. Veriler Diyanet'in kendi namaz vakitleri sitesinden gelir (sunucuda oluşturulan sayfalar + bölge listesi JSON'u) — giriş yok, API anahtarı yok, salt okunur. Bu sunucu **resmi çizelgeyi** verir, hesaplanmış bir yaklaşımı değil: genel namaz vakti sunucuları vakitleri hesaplar (Aladhan 13. yöntem "Diyanet" resmi vakitlerden bir-iki dakika sapabilir) ve Diyanet tabanlı diğer tek araç yalnızca 20 şehri kapsar.

## Yapay zekâ ajanları için

- **Yerler**: bir il (`"Ankara"`), bir il/ilçe (`"İstanbul/Beylikdüzü"`, `"Ankara/Çankaya"`) veya sayısal ilçe kodu (`"9541"`, İstanbul). Yalnızca il verilirse merkez ilçe döner.
- **İsimler Türkçe duyarsızdır**: `"Cankaya"` `"ÇANKAYA"`yı, `"istanbul"` `"İSTANBUL"`u bulur. Türkçe ve İngilizce isimler çalışır.
- **Merkeze bağlı ilçeler**: Diyanet her ilçe için ayrı çizelge yayımlamaz — bir ilin şehir içi ilçeleri (ör. Ankara'nın Çankaya'sı) merkez ilçeye bağlıdır. Araçlar bunları merkez çizelgeye çözer ve yanıtta belirtir (`requested_district` + `note`); hizmet verilen ilçe her zaman bildirilir.
- **Diller**: `lang` `"tr"` (varsayılan), `"en"`, `"ar"`, `"de"` veya `"fr"` — sitenin kendi dil sürümleri. Vakitler tüm dillerde aynıdır.
- **Yıllık tablo**: `diyanet_yearly_times` tam takvim yılını verir (365 satır) — önce gelen ay, sonra 1 Ocak'tan yılın geri kalanı. Her satırda Miladi + Hicri tarih vardır.
- Her yanıt `fetched_at` (UTC) ve `source: namazvakitleri.diyanet.gov.tr` taşır. Vakitler Avrupa/İstanbul yerel saatidir.

## Kurulum

```bash
uvx diyanet-mcp
```

Veya MCP istemci yapılandırmanıza ekleyin (ör. Claude Desktop):

```json
{
  "mcpServers": {
    "diyanet": {
      "command": "uvx",
      "args": ["diyanet-mcp"]
    }
  }
}
```

## Araçlar

| Araç | Ne yapar |
| --- | --- |
| `diyanet_prayer_times` | Bir yer için bugünün 6 vakti (imsak, gunes, ogle, ikindi, aksam, yatsi) + Miladi/Hicri tarihler + kıble açısı/saati + astronomik gün doğumu/batımı |
| `diyanet_yearly_times` | Yıllık tablo: günde bir satır (Miladi + Hicri + 6 vakit), 365 satır (limit 1–365) |
| `diyanet_list_provinces` | 81 il, Diyanet kodları ve Türkçe + İngilizce isimleriyle (isteğe bağlı alt dize filtresi) |
| `diyanet_list_districts` | Bir ilin ilçeleri (isim veya kodla), kodları, isimleri ve sayfa adresleriyle |
| `diyanet_qibla` | Bir yer için kıble açısı (kuzeyden derece), kıble saati, astronomik gün doğumu/batımı |
| `diyanet_health` | Diyanet'in namaz vakitleri sitesine şu an ulaşılabiliyor mu? |

## Örnek

İstanbul, 17 Kasım 2026 (8 Cemaziyelahir 1448):

```json
{ "place": "İstanbul", "ilce_id": 9541,
  "times": { "imsak": "06:18", "gunes": "07:47", "ogle": "12:54",
             "ikindi": "15:28", "aksam": "17:51", "yatsi": "19:15" },
  "qibla_angle_deg": 147, "qibla_time": "11:01" }
```

## Uyarılar

- Vakitler Diyanet'in resmi çizelgesidir — kullanmadan önce namazvakitleri.diyanet.gov.tr adresinden doğrulayın.
- Diyanet Ankara için yalnızca 17 ilçe listeler (şehir içi ilçeler merkez çizelgeyi paylaşır); araçlar hizmet verilen ilçeyi bildirir.
- Yıllık tablonun satır sırası sayfanın sırasıdır (önce gelen ay, sonra 1 Ocak'tan itibaren) — her satır kendi tarihini taşır, kronoloji gerekirse tarihe göre sıralayın.
- Aktarım, düz istek yedeğiyle Chrome TLS kimliğine bürünme kullanır; istekler ~0,5 sn arayla gönderilir.

## Geliştirme

```bash
python -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/python -m pytest tests/test_places.py -v   # çevrimdışı, kayıtlı örnekler
.venv/bin/python -m pytest tests/test_live.py -v     # canlı, namazvakitleri.diyanet.gov.tr
.venv/bin/python tests/smoke_live.py                 # günlük CI denetimi
```

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
