package com.apiece.springboot_sns_sample.domain.recommend;

import com.apiece.springboot_sns_sample.domain.post.Post;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.Repository;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;

public interface RecommendRepository extends Repository<Post, Long> {

    @Query("""
            select p from Post p join fetch p.user
            where p.id in :ids and p.deletedAt is null
            and p.parentId is null and p.repostId is null
            """)
    List<Post> visible(@Param("ids") List<Long> ids);

    @Query("""
            select p from Post p join fetch p.user
            where p.deletedAt is null and p.parentId is null and p.repostId is null
            and (p.createdAt < :before or (p.createdAt = :before and p.id < :id))
            order by p.createdAt desc, p.id desc
            """)
    List<Post> latest(@Param("before") LocalDateTime before, @Param("id") long id, Pageable pageable);
}
