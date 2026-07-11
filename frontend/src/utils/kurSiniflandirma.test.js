import { kurNo, kurSinifi, kurRenkSinifi } from "./kurSiniflandirma";

describe("kurNo — kur string'inden numara", () => {
  test("düz sayı / 'Kur N' / sayısal", () => {
    expect(kurNo("1")).toBe(1);
    expect(kurNo("3")).toBe(3);
    expect(kurNo("Kur 3")).toBe(3);
    expect(kurNo(2)).toBe(2);
  });
  test("boş/çözülemez → null", () => {
    expect(kurNo("")).toBeNull();
    expect(kurNo(null)).toBeNull();
    expect(kurNo(undefined)).toBeNull();
    expect(kurNo("Kur")).toBeNull();
  });
});

describe("kurSinifi — kur=1 yeni / kur>1 üst kur", () => {
  test("kur=1 → yeni", () => {
    expect(kurSinifi("1")).toBe("yeni");
    expect(kurSinifi(1)).toBe("yeni");
  });
  test("kur>1 → ust_kur (ilk kez eklenmiş olsa bile)", () => {
    expect(kurSinifi("2")).toBe("ust_kur");
    expect(kurSinifi("Kur 5")).toBe("ust_kur");
    expect(kurSinifi(3)).toBe("ust_kur");
  });
  test("belirsiz → null", () => {
    expect(kurSinifi("")).toBeNull();
    expect(kurSinifi(null)).toBeNull();
  });
});

describe("kurRenkSinifi — MOR / YEŞİL", () => {
  test("kur=1 → mor (bg-purple-50)", () => {
    expect(kurRenkSinifi("1")).toBe("bg-purple-50");
  });
  test("kur>1 → yeşil (bg-emerald-50)", () => {
    expect(kurRenkSinifi("2")).toBe("bg-emerald-50");
    expect(kurRenkSinifi("Kur 4")).toBe("bg-emerald-50");
  });
  test("belirsiz → boş sınıf", () => {
    expect(kurRenkSinifi("")).toBe("");
    expect(kurRenkSinifi(null)).toBe("");
  });
});
