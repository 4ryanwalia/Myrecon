package com.aryan.myrecon

import com.aryan.myrecon.data.GeoIntel
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

/**
 * The GPS-to-place chain, against the live keyless services it depends on.
 *
 * This is the substitute for visual landmark recognition, so it has to actually
 * name places — "it returned without throwing" would not be evidence of that.
 */
class GeoIntelTest {

    @Test
    fun `coordinate validation rejects the usual junk`() {
        assertTrue(GeoIntel.validCoords(51.5, -0.12))
        assertTrue(GeoIntel.validCoords(-33.87, 151.21))
        // 0,0 is overwhelmingly a zeroed GPS field, not the Gulf of Guinea.
        assertFalse(GeoIntel.validCoords(0.0, 0.0))
        assertFalse(GeoIntel.validCoords(91.0, 0.0))
        assertFalse(GeoIntel.validCoords(0.0, 181.0))
        assertFalse(GeoIntel.validCoords(null, null))
        assertFalse(GeoIntel.validCoords(51.5, null))
    }

    @Test
    fun `big ben resolves from coordinates alone`() = runBlocking {
        val r = GeoIntel.investigate(51.500729, -0.124625)
        println("place     : ${r.place.name}")
        println("address   : ${r.place.displayName?.take(90)}")
        println("country   : ${r.place.country} (${r.place.countryCode})")
        println("wikidata  : ${r.place.wikidata}")
        println("article   : ${r.article?.title}")
        println("nearby    : ${r.nearby.take(4).map { "${it.title} ${it.distanceM.toInt()}m" }}")
        println("confidence: ${r.confidence} (${r.confidenceLabel})")

        assertTrue("place should resolve", r.place.found)
        assertNotNull("a named feature is the whole point", r.place.name)
        assertEquals("United Kingdom", r.place.country)
        assertEquals("GB", r.place.countryCode)
        assertNotNull("Wikidata id should come through extratags", r.place.wikidata)
        assertTrue("expected nearby notable places", r.nearby.size >= 4)
        assertNotNull("an article should resolve", r.article)
        assertTrue("expected an article extract", !r.article!!.extract.isNullOrBlank())
        assertEquals("high", r.confidenceLabel)
        assertTrue("map link should be built", r.mapsUrl.contains("openstreetmap"))
    }

    @Test
    fun `nearby places are ordered by distance`() = runBlocking {
        val r = GeoIntel.investigate(48.858370, 2.294481) // Eiffel Tower
        println("eiffel place : ${r.place.name} / ${r.place.city}")
        println("eiffel nearby: ${r.nearby.take(3).map { it.title }}")
        assertTrue(r.place.found)
        assertEquals("France", r.place.country)
        val distances = r.nearby.map { it.distanceM }
        assertEquals("nearest first", distances.sorted(), distances)
        r.nearby.forEach { assertTrue("url should be built", it.url.startsWith("https://")) }
    }

    @Test
    fun `open ocean degrades honestly instead of inventing a place`() = runBlocking {
        val r = GeoIntel.investigate(30.0, -40.0)
        println("atlantic: found=${r.place.found} confidence=${r.confidence} nearby=${r.nearby.size}")
        assertTrue("confidence must collapse", r.confidence < 40)
        assertEquals("low", r.confidenceLabel)
    }

    @Test
    fun `null island returns an error rather than a location`() = runBlocking {
        val r = GeoIntel.investigate(0.0, 0.0)
        assertFalse(r.place.found)
        assertNotNull(r.error)
        assertEquals(0, r.confidence)
    }
}
